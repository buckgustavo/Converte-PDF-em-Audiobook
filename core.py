import asyncio
import os
import re
import subprocess
import tempfile
import threading

import PyPDF2
import pytesseract
import edge_tts
from pdf2image import convert_from_path

def _run_async(coro):
    result = [None]
    exc = [None]
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            exc[0] = e
        finally:
            loop.close()
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if exc[0]:
        raise exc[0]
    return result[0]


VOICE_MAP = {
    ("pt", "com.br"): "pt-BR-AntonioNeural",
    ("pt", "com"):    "pt-PT-DuarteNeural",
    ("pt", "co.uk"):  "pt-PT-DuarteNeural",
    ("pt", "com.au"): "pt-PT-DuarteNeural",
    ("en", "com"):    "en-US-AriaNeural",
    ("en", "co.uk"):  "en-GB-RyanNeural",
    ("en", "com.au"): "en-AU-NatashaNeural",
    ("en", "com.br"): "en-US-AriaNeural",
    ("es", "com"):    "es-ES-AlvaroNeural",
    ("es", "com.br"): "es-MX-JorgeNeural",
    ("es", "co.uk"):  "es-ES-AlvaroNeural",
    ("fr", "com"):    "fr-FR-DeniseNeural",
    ("fr", "com.br"): "fr-FR-DeniseNeural",
    ("de", "com"):    "de-DE-ConradNeural",
    ("de", "com.br"): "de-DE-ConradNeural",
}


def _get_voice(idioma, sotaque):
    return VOICE_MAP.get((idioma, sotaque), VOICE_MAP.get((idioma, "com"), "pt-BR-AntonioNeural"))


def extrair_texto_digital(caminho_pdf, progress_cb=None):
    texto = ""
    with open(caminho_pdf, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)
        for i, page in enumerate(reader.pages):
            t = page.extract_text()
            if t:
                texto += t + " "
            if progress_cb:
                progress_cb(int((i + 1) / total * 100), f"Lendo página {i+1}/{total}...")
    return texto.strip()


def extrair_texto_ocr(caminho_pdf, idioma="pt", progress_cb=None):
    if progress_cb:
        progress_cb(0, "PDF escaneado detectado — usando OCR...")
    paginas = convert_from_path(caminho_pdf, dpi=200)
    texto = ""
    lang_ocr = "por" if idioma == "pt" else "eng"
    for i, pagina in enumerate(paginas):
        pagina_cinza = pagina.convert("L")
        t = pytesseract.image_to_string(pagina_cinza, lang=lang_ocr)
        texto += t + " "
        if progress_cb:
            progress_cb(int((i + 1) / len(paginas) * 100), f"OCR: página {i+1}/{len(paginas)}")
    return texto.strip()


def extrair_texto(caminho_pdf, idioma="pt", progress_cb=None):
    texto = extrair_texto_digital(caminho_pdf, progress_cb)
    if len(texto.split()) < 50:
        texto = extrair_texto_ocr(caminho_pdf, idioma, progress_cb)
    return texto


def limpar_texto(texto, remover_codigo=True):
    linhas = texto.split("\n")
    linhas = [l for l in linhas if len(l.strip()) > 40]
    texto = "\n".join(linhas)

    if remover_codigo:
        padroes_codigo = [
            r"^\s*(def |class |import |from |return |if |else:|elif |for |while |try:|except|with |print\()",
            r"^\s*[a-zA-Z_]+\s*=\s*.+[;{}\[\]]",
            r"^\s*[{}();]+\s*$",
            r"^\s*\/\/",
            r"^\s*#",
            r"^\s*<!--",
        ]
        linhas_filtradas = []
        for linha in texto.split("\n"):
            if not any(re.match(p, linha) for p in padroes_codigo):
                linhas_filtradas.append(linha)
        texto = "\n".join(linhas_filtradas)

    texto = re.sub(r"http\S+", "", texto)
    texto = re.sub(r"[•►▶▸●◆→\|]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r" {2,}", " ", texto)
    return texto.strip()


def dividir_texto(texto, tamanho=1800):
    chunks = []
    while len(texto) > tamanho:
        corte = texto.rfind(".", 0, tamanho)
        if corte == -1:
            corte = tamanho
        chunks.append(texto[: corte + 1].strip())
        texto = texto[corte + 1 :].strip()
    if texto:
        chunks.append(texto)
    return chunks


async def _gerar_chunks_paralelo(chunks, voz, velocidade_lenta, tmp_dir, progress_cb=None):
    arquivos = [None] * len(chunks)
    concluidos = [0]
    semaforo = asyncio.Semaphore(8)
    rate = "-15%" if velocidade_lenta else "+0%"

    async def processar(i, chunk):
        async with semaforo:
            caminho = os.path.join(tmp_dir, f"parte_{i:04d}.mp3")
            for tentativa in range(3):
                try:
                    communicate = edge_tts.Communicate(chunk, voz, rate=rate)
                    await communicate.save(caminho)
                    arquivos[i] = caminho
                    break
                except Exception:
                    if tentativa < 2:
                        await asyncio.sleep(1 * (tentativa + 1))
            concluidos[0] += 1
            if progress_cb:
                pct = 40 + int(concluidos[0] / len(chunks) * 50)
                progress_cb(pct, f"Gerando áudio {concluidos[0]}/{len(chunks)}...")

    await asyncio.gather(*[processar(i, chunk) for i, chunk in enumerate(chunks)])
    return [a for a in arquivos if a is not None]


def _concatenar_mp3(arquivos, output_path):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for arq in arquivos:
            f.write(f"file '{arq}'\n")
        lista = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", output_path],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        from pydub import AudioSegment
        audio = AudioSegment.empty()
        for arq in arquivos:
            audio += AudioSegment.from_mp3(arq)
        audio.export(output_path, format="mp3")
    finally:
        os.unlink(lista)


def gerar_audio(
    caminho_pdf,
    output_path,
    idioma="pt",
    sotaque="com.br",
    velocidade_lenta=False,
    chunk_size=1800,
    remover_codigo=True,
    progress_cb=None,
):
    def prog(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    prog(5, "Extraindo texto do PDF...")
    texto = extrair_texto(
        caminho_pdf,
        idioma,
        lambda p, m: prog(int(5 + p * 0.25), m),
    )

    if not texto:
        raise ValueError("Não foi possível extrair texto do PDF.")

    prog(30, "Limpando texto...")
    texto = limpar_texto(texto, remover_codigo)
    word_count = len(texto.split())

    prog(35, f"Dividindo em chunks ({word_count} palavras)...")
    chunks = dividir_texto(texto, chunk_size)

    voz = _get_voice(idioma, sotaque)
    prog(38, f"Voz selecionada: {voz} — {len(chunks)} partes em paralelo...")

    with tempfile.TemporaryDirectory() as tmp:
        arquivos = _run_async(
            _gerar_chunks_paralelo(chunks, voz, velocidade_lenta, tmp, progress_cb=prog)
        )

        if not arquivos:
            raise ValueError("Nenhum áudio foi gerado.")

        prog(90, "Juntando partes...")
        _concatenar_mp3(arquivos, output_path)

    prog(100, "Concluído!")
    return word_count
