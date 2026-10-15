"""Montagem do audiobook: silêncios, concatenação e capítulos (MP3 com ID3 CHAP ou M4B)."""

import os
import shutil
import subprocess

from mutagen.id3 import CHAP, CTOC, ID3, TALB, TIT2, TPE1, CTOCFlags
from mutagen.mp3 import MP3

FFMPEG = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg") or "ffmpeg"

# Mesmo formato que o Edge TTS entrega (24 kHz, mono, 48 kbps) para concatenar sem recodificar
_MP3_ARGS = ["-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k"]


def _ffmpeg(*args):
    try:
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg não encontrado. Instale o ffmpeg no servidor.") from None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg falhou: {e.stderr.decode(errors='ignore')[-500:]}") from None


def silencio(pasta, ms):
    caminho = os.path.join(pasta, f"silencio_{ms}.mp3")
    if not os.path.exists(caminho):
        _ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{ms / 1000:.3f}", *_MP3_ARGS, caminho)
    return caminho


def duracao(caminho):
    return MP3(caminho).info.length


def _escapar_concat(caminho):
    return "file '" + caminho.replace("'", "'\\''") + "'\n"


def _escapar_meta(texto):
    for c in ("\\", "=", ";", "#", "\n"):
        texto = texto.replace(c, "\\" + c)
    return texto


def montar(partes, saida, formato="mp3", titulo="Audiobook", pasta_tmp=None):
    """partes: lista de (caminho_mp3, capitulo|None). Devolve (duracao_total, [(capitulo, inicio_s)])."""
    pasta_tmp = pasta_tmp or os.path.dirname(saida)
    capitulos, t = [], 0.0
    lista = os.path.join(pasta_tmp, "concat.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for caminho, capitulo in partes:
            if capitulo:
                capitulos.append((capitulo, t))
            t += duracao(caminho)
            f.write(_escapar_concat(caminho))
    total = t

    if formato == "m4b":
        meta = os.path.join(pasta_tmp, "meta.txt")
        with open(meta, "w", encoding="utf-8") as f:
            f.write(f";FFMETADATA1\ntitle={_escapar_meta(titulo)}\nartist=Edge TTS\ngenre=Audiobook\n")
            for i, (nome, inicio) in enumerate(capitulos):
                fim = capitulos[i + 1][1] if i + 1 < len(capitulos) else total
                f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(inicio * 1000)}\nEND={int(fim * 1000)}\n"
                        f"title={_escapar_meta(nome)}\n")
        _ffmpeg("-f", "concat", "-safe", "0", "-i", lista, "-i", meta, "-map", "0:a",
                "-map_metadata", "1", "-map_chapters", "1", "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart", "-f", "mp4", saida)
    else:
        _ffmpeg("-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", saida)
        _tags_mp3(saida, titulo, capitulos, total)

    return total, capitulos


def _tags_mp3(caminho, titulo, capitulos, total):
    tags = ID3()
    tags.add(TIT2(encoding=3, text=titulo))
    tags.add(TALB(encoding=3, text=titulo))
    tags.add(TPE1(encoding=3, text="Edge TTS"))
    ids = []
    for i, (nome, inicio) in enumerate(capitulos):
        fim = capitulos[i + 1][1] if i + 1 < len(capitulos) else total
        cid = f"ch{i}"
        ids.append(cid)
        tags.add(CHAP(element_id=cid, start_time=int(inicio * 1000), end_time=int(fim * 1000),
                      sub_frames=[TIT2(encoding=3, text=nome)]))
    if ids:
        tags.add(CTOC(element_id="toc", flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
                      child_element_ids=ids, sub_frames=[TIT2(encoding=3, text="Capítulos")]))
    tags.save(caminho)
