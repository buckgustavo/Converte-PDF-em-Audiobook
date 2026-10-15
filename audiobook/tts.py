"""Síntese de voz com Edge TTS em paralelo, com retry e cancelamento."""

import asyncio
import os

import edge_tts

TENTATIVAS = 5
CONCORRENCIA = int(os.environ.get("TTS_CONCURRENCY", "6"))


class ErroTTS(RuntimeError):
    pass


def formatar_rate(velocidade):
    """Converte um percentual inteiro (-50..+100) no formato do Edge TTS ("+10%")."""
    return f"{int(velocidade):+d}%"


async def _salvar(texto, voz, rate, caminho):
    ultimo_erro = None
    for tentativa in range(TENTATIVAS):
        try:
            await edge_tts.Communicate(texto, voz, rate=rate).save(caminho)
            if os.path.getsize(caminho) > 0:
                return
            ultimo_erro = "áudio vazio"
        except Exception as e:
            ultimo_erro = e
        await asyncio.sleep(min(2 ** tentativa, 10))
    raise ErroTTS(f"Falha ao gerar áudio após {TENTATIVAS} tentativas ({ultimo_erro}). Trecho: {texto[:80]!r}")


async def sintetizar(itens, pasta, velocidade=0, progress_cb=None, cancelado=None):
    """itens: lista de (texto, voz). Devolve a lista de caminhos MP3 na mesma ordem."""
    rate = formatar_rate(velocidade)
    semaforo = asyncio.Semaphore(CONCORRENCIA)
    caminhos = [os.path.join(pasta, f"parte_{i:05d}.mp3") for i in range(len(itens))]
    concluidos = 0

    async def processar(i, texto, voz):
        nonlocal concluidos
        async with semaforo:
            if cancelado and cancelado():
                raise InterruptedError
            await _salvar(texto, voz, rate, caminhos[i])
            concluidos += 1
            if progress_cb:
                progress_cb(concluidos, len(itens))

    async with asyncio.TaskGroup() as tg:
        for i, (texto, voz) in enumerate(itens):
            tg.create_task(processar(i, texto, voz))
    return caminhos


def sintetizar_sync(itens, pasta, velocidade=0, progress_cb=None, cancelado=None):
    try:
        return asyncio.run(sintetizar(itens, pasta, velocidade, progress_cb, cancelado))
    except ExceptionGroup as eg:
        # Propaga o primeiro erro "real" (cancelamento tem prioridade)
        for tipo in (InterruptedError, ErroTTS):
            sub = eg.subgroup(tipo)
            if sub:
                raise sub.exceptions[0] from None
        raise eg.exceptions[0] from None


async def amostra(texto, voz, velocidade=0):
    """Gera um MP3 curto em memória (prévia da voz)."""
    audio = bytearray()
    async for chunk in edge_tts.Communicate(texto, voz, rate=formatar_rate(velocidade)).stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)
