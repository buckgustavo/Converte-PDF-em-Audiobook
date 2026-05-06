import json
import os
import queue
import tempfile
import uuid
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core import gerar_audio

app = FastAPI(title="PDF para Audiobook")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OUTPUT_DIR = Path(tempfile.gettempdir()) / "pdf2mp3_jobs"
OUTPUT_DIR.mkdir(exist_ok=True)

jobs: dict = {}
job_queues: dict = {}


def _run_job(job_id: str, pdf_path: str, output_path: str, params: dict):
    q = job_queues[job_id]

    def progress_cb(pct: int, msg: str):
        q.put({"type": "progress", "pct": pct, "msg": msg})

    try:
        jobs[job_id]["status"] = "running"
        word_count = gerar_audio(
            pdf_path,
            output_path,
            idioma=params["idioma"],
            sotaque=params["sotaque"],
            velocidade_lenta=params["velocidade_lenta"],
            chunk_size=params["chunk_size"],
            remover_codigo=params["remover_codigo"],
            progress_cb=progress_cb,
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["word_count"] = word_count
        q.put({"type": "done", "word_count": word_count})
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        q.put({"type": "error", "msg": str(e)})
    finally:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    idioma: str = Form("pt"),
    sotaque: str = Form("com.br"),
    velocidade_lenta: bool = Form(False),
    chunk_size: int = Form(1800),
    remover_codigo: bool = Form(True),
):
    job_id = str(uuid.uuid4())
    pdf_path = str(OUTPUT_DIR / f"{job_id}.pdf")
    output_path = str(OUTPUT_DIR / f"{job_id}.mp3")

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    original_name = (file.filename or "audiobook.pdf").replace(".pdf", ".mp3")

    jobs[job_id] = {
        "status": "queued",
        "original_name": original_name,
        "output_path": output_path,
    }
    job_queues[job_id] = queue.Queue()

    params = {
        "idioma": idioma,
        "sotaque": sotaque,
        "velocidade_lenta": velocidade_lenta,
        "chunk_size": chunk_size,
        "remover_codigo": remover_codigo,
    }
    Thread(target=_run_job, args=(job_id, pdf_path, output_path, params), daemon=True).start()

    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
def progress_stream(job_id: str):
    if job_id not in jobs:
        return StreamingResponse(
            iter([f'data: {json.dumps({"type":"error","msg":"Job não encontrado"})}\n\n']),
            media_type="text/event-stream",
        )

    q = job_queues[job_id]

    def generate():
        while True:
            try:
                event = q.get(timeout=10)
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ("done", "error"):
                    break
            except queue.Empty:
                yield 'data: {"type":"ping"}\n\n'
                continue

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/download/{job_id}")
def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Job não disponível"}, status_code=404)
    return FileResponse(
        job["output_path"],
        media_type="audio/mpeg",
        filename=job["original_name"],
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
