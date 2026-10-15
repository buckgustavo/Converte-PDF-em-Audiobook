import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from audiobook import Opcoes, gerar_audiobook
from audiobook import tts, voices

DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/pdf2audiobook"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
JOB_TTL_HOURS = float(os.environ.get("JOB_TTL_HOURS", "6"))

log = logging.getLogger("audiobook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass
class Job:
    id: str
    nome: str
    formato: str
    status: str = "queued"  # queued | running | done | error | canceled
    pct: int = 0
    msg: str = "Na fila..."
    criado: float = field(default_factory=time.time)
    finalizado: float | None = None
    resultado: dict | None = None
    erro: str | None = None
    cancelar: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def pdf(self):
        return DATA_DIR / f"{self.id}.pdf"

    @property
    def saida(self):
        return DATA_DIR / f"{self.id}.{self.formato}"

    def publico(self):
        d = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "cancelar"}
        d["fila"] = _posicao_na_fila(self.id) if self.status == "queued" else 0
        return d


jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)


def _posicao_na_fila(job_id):
    with jobs_lock:
        fila = sorted((j for j in jobs.values() if j.status == "queued"), key=lambda j: j.criado)
    return next((i + 1 for i, j in enumerate(fila) if j.id == job_id), 0)


def _executar(job: Job, op: Opcoes):
    if job.cancelar.is_set():
        return
    job.status = "running"

    def progress_cb(pct, msg):
        job.pct, job.msg = pct, msg

    try:
        r = gerar_audiobook(str(job.pdf), str(job.saida), op, progress_cb, job.cancelar.is_set)
        job.resultado = {"palavras": r.palavras, "duracao": r.duracao, "capitulos": r.capitulos, "avisos": r.avisos}
        job.pct, job.msg, job.status = 100, "Concluído!", "done"
    except InterruptedError:
        job.status, job.msg = "canceled", "Cancelado."
        job.saida.unlink(missing_ok=True)
    except Exception as e:
        log.exception("Job %s falhou", job.id)
        job.status, job.erro = "error", str(e)
        job.saida.unlink(missing_ok=True)
    finally:
        job.finalizado = time.time()
        job.pdf.unlink(missing_ok=True)


def _limpeza_periodica(parar: threading.Event):
    while not parar.wait(600):
        limite = time.time() - JOB_TTL_HOURS * 3600
        with jobs_lock:
            velhos = [j for j in jobs.values() if j.finalizado and j.finalizado < limite]
            for j in velhos:
                del jobs[j.id]
        for j in velhos:
            j.saida.unlink(missing_ok=True)
        if velhos:
            log.info("Limpeza: %d jobs antigos removidos", len(velhos))


@asynccontextmanager
async def lifespan(_app):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for padrao in ("*.pdf", "*.mp3", "*.m4b"):  # sobras de execuções anteriores
        for f in DATA_DIR.glob(padrao):
            f.unlink(missing_ok=True)
    parar = threading.Event()
    threading.Thread(target=_limpeza_periodica, args=(parar,), daemon=True).start()
    yield
    parar.set()
    for j in jobs.values():
        j.cancelar.set()
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="PDF para Audiobook", lifespan=lifespan)


def _job_ou_404(job_id) -> Job:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado (pode ter expirado).")
    return job


@app.get("/healthz")
def healthz():
    return {"ok": True, "jobs_ativos": sum(1 for j in jobs.values() if j.status in ("queued", "running"))}


@app.get("/api/voices")
def listar_vozes():
    return {
        "idiomas": {k: v["nome"] for k, v in voices.IDIOMAS.items()},
        "vozes": voices.listar_vozes(),
        "padrao": voices.VOZ_PADRAO,
    }


@app.post("/api/preview")
async def preview(voz: str = Form(...), velocidade: int = Form(0), texto: str = Form("")):
    if not voices.voz_valida(voz):
        raise HTTPException(400, "Voz inválida.")
    texto = texto.strip()[:300] or voices.AMOSTRAS[voices.idioma_da_voz(voz)]
    try:
        audio = await tts.amostra(texto, voz, max(-50, min(100, velocidade)))
    except Exception as e:
        raise HTTPException(502, f"Falha ao gerar a prévia: {e}")
    return Response(audio, media_type="audio/mpeg")


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    voz: str = Form(""),
    idioma: str = Form("pt"),
    velocidade: int = Form(0),
    voz_destaque: bool = Form(True),
    modo_tecnico: bool = Form(True),
    codigo: str = Form("anunciar"),
    pagina_inicio: int | None = Form(None),
    pagina_fim: int | None = Form(None),
    chunk_size: int = Form(1800),
    formato: str = Form("mp3"),
):
    nome = Path(file.filename or "audiobook.pdf").stem or "audiobook"
    op = Opcoes(
        idioma=idioma, voz=voz or None, velocidade=velocidade, voz_destaque=voz_destaque,
        modo_tecnico=modo_tecnico, codigo=codigo, pagina_inicio=pagina_inicio,
        pagina_fim=pagina_fim, chunk_size=chunk_size, formato=formato, titulo=nome,
    )
    job = Job(id=uuid.uuid4().hex, nome=nome, formato=op.formato)

    # Grava em blocos, respeitando o limite de tamanho
    limite, tamanho = MAX_UPLOAD_MB * 1024 * 1024, 0
    with open(job.pdf, "wb") as f:
        while bloco := await file.read(1024 * 1024):
            tamanho += len(bloco)
            if tamanho > limite:
                f.close()
                job.pdf.unlink(missing_ok=True)
                raise HTTPException(413, f"Arquivo maior que o limite de {MAX_UPLOAD_MB} MB.")
            f.write(bloco)
    with open(job.pdf, "rb") as f:
        if f.read(5) != b"%PDF-":
            job.pdf.unlink(missing_ok=True)
            raise HTTPException(400, "O arquivo enviado não é um PDF válido.")

    with jobs_lock:
        jobs[job.id] = job
    executor.submit(_executar, job, op)
    log.info("Job %s criado: %s (%.1f MB)", job.id, nome, tamanho / 1048576)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def status(job_id: str):
    return _job_ou_404(job_id).publico()


@app.delete("/api/jobs/{job_id}")
def cancelar(job_id: str):
    job = _job_ou_404(job_id)
    job.cancelar.set()
    if job.status == "queued":
        job.status, job.msg, job.finalizado = "canceled", "Cancelado.", time.time()
        job.pdf.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    """SSE que lê o estado do job — reconectar a qualquer momento é seguro."""
    job = _job_ou_404(job_id)

    async def gerar():
        ultimo, ociosidade = None, 0.0
        while True:
            estado = job.publico()
            chave = (estado["status"], estado["pct"], estado["msg"], estado["fila"])
            if chave != ultimo:
                ultimo, ociosidade = chave, 0.0
                yield f"data: {json.dumps(estado, ensure_ascii=False)}\n\n"
            elif ociosidade >= 15:
                ociosidade = 0.0
                yield ": ping\n\n"
            if estado["status"] in ("done", "error", "canceled"):
                break
            await asyncio.sleep(0.5)
            ociosidade += 0.5

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/download/{job_id}")
def download(job_id: str):
    job = _job_ou_404(job_id)
    if job.status != "done" or not job.saida.exists():
        raise HTTPException(404, "Áudio não disponível.")
    nome = re.sub(r'[\\/:*?"<>|]+', "_", job.nome)
    mime = "audio/mp4" if job.formato == "m4b" else "audio/mpeg"
    return FileResponse(job.saida, media_type=mime, filename=f"{nome}.{job.formato}")


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
