"""Pipeline completo: PDF -> blocos -> roteiro de narração -> TTS -> audiobook."""

import re
import tempfile
from dataclasses import dataclass, field

from . import audio, extract, text, tts, voices

PAUSA_CAPITULO = 2000
PAUSA_TITULO = (1000, 600)
PAUSA_DESTAQUE = (500, 500)
PAUSA_CODIGO = (400, 400)


@dataclass
class Opcoes:
    idioma: str = "pt"
    voz: str | None = None
    velocidade: int = 0                # percentual, -50..+100
    voz_destaque: bool = True          # voz alternativa para títulos, dicas e código
    modo_tecnico: bool = True          # pronúncia de termos técnicos, identificadores, dicas
    codigo: str = "anunciar"           # "anunciar" | "omitir" | "ler"
    pagina_inicio: int | None = None
    pagina_fim: int | None = None
    chunk_size: int = 1800
    formato: str = "mp3"               # "mp3" | "m4b"
    titulo: str = "Audiobook"

    def __post_init__(self):
        if self.voz and voices.voz_valida(self.voz):
            self.idioma = voices.idioma_da_voz(self.voz)
        else:
            self.idioma = self.idioma if self.idioma in voices.IDIOMAS else "pt"
            self.voz = voices.VOZ_PADRAO[self.idioma]
        self.velocidade = max(-50, min(100, int(self.velocidade)))
        self.chunk_size = max(300, min(4000, int(self.chunk_size)))
        if self.codigo not in ("anunciar", "omitir", "ler"):
            self.codigo = "anunciar"
        if self.formato not in ("mp3", "m4b"):
            self.formato = "mp3"


@dataclass
class Segmento:
    texto: str
    destaque: bool = False
    pausa_antes: int = 0
    pausa_depois: int = 0
    capitulo: str | None = None


@dataclass
class Resultado:
    palavras: int
    duracao: float
    capitulos: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _frase(t):
    t = t.strip()
    return t if re.search(r"[.!?:…]$", t) else t + "."


def montar_roteiro(blocos, op: Opcoes):
    """Converte os blocos extraídos em segmentos narráveis."""
    roteiro = []
    capitulo_pendente = None

    def add(seg):
        nonlocal capitulo_pendente
        if not re.search(r"\w", seg.texto):
            return
        if capitulo_pendente:
            seg.capitulo, capitulo_pendente = capitulo_pendente, None
            seg.pausa_antes = max(seg.pausa_antes, PAUSA_CAPITULO)
        # Parágrafos de narração seguidos viram um só segmento (menos requisições, fala contínua)
        ant = roteiro[-1] if roteiro else None
        if ant and not seg.destaque and not ant.destaque and not seg.capitulo and not seg.pausa_antes and not ant.pausa_depois:
            ant.texto += " " + seg.texto
        else:
            roteiro.append(seg)

    for b in blocos:
        if b.capitulo:
            capitulo_pendente = b.capitulo
        if b.tipo == "titulo":
            t = text.preparar_paragrafo(b.texto, op.idioma, op.modo_tecnico)
            add(Segmento(_frase(t), True, *PAUSA_TITULO))
        elif b.tipo == "codigo":
            fala = text.narrar_codigo(b.texto, op.idioma, op.codigo)
            if fala:
                add(Segmento(fala, True, *PAUSA_CODIGO))
        else:
            t = text.preparar_paragrafo(b.texto, op.idioma, op.modo_tecnico)
            dica = text.destaque(t) if op.modo_tecnico else None
            if dica:
                add(Segmento(_frase(dica), True, *PAUSA_DESTAQUE))
            else:
                add(Segmento(t))
    return roteiro


def gerar_audiobook(caminho_pdf, saida, op: Opcoes, progress_cb=None, cancelado=None):
    def prog(pct, msg):
        if progress_cb:
            progress_cb(int(pct), msg)

    def checar():
        if cancelado and cancelado():
            raise InterruptedError

    prog(1, "Abrindo PDF...")
    blocos, avisos = extract.extrair(
        caminho_pdf,
        voices.IDIOMAS[op.idioma]["ocr"],
        op.pagina_inicio,
        op.pagina_fim,
        progress_cb=lambda p, m: prog(1 + p * 0.29, m),
        cancelado=cancelado,
    )
    checar()

    prog(31, "Preparando narração...")
    roteiro = montar_roteiro(blocos, op)
    if not roteiro:
        raise ValueError(" ".join(["Não foi possível extrair texto do PDF.", *avisos]))
    palavras = sum(len(s.texto.split()) for s in roteiro)
    capitulos = sum(1 for s in roteiro if s.capitulo)

    voz_destaque = voices.voz_alternativa(op.voz) if op.voz_destaque else op.voz
    itens, plano = [], []  # plano: ("tts", idx, capitulo) | ("pausa", ms, None)
    for s in roteiro:
        if s.pausa_antes:
            plano.append(("pausa", s.pausa_antes, s.capitulo))
        for i, pedaco in enumerate(text.dividir_texto(s.texto, op.chunk_size)):
            cap = s.capitulo if i == 0 and not s.pausa_antes else None
            plano.append(("tts", len(itens), cap))
            itens.append((pedaco, voz_destaque if s.destaque else op.voz))
        if s.pausa_depois:
            plano.append(("pausa", s.pausa_depois, None))

    n_palavras = f"{palavras:,}".replace(",", ".")
    prog(35, f"{n_palavras} palavras, {capitulos} capítulos — gerando {len(itens)} trechos de áudio...")

    with tempfile.TemporaryDirectory(prefix="audiobook_") as tmp:
        arquivos = tts.sintetizar_sync(
            itens, tmp, op.velocidade,
            progress_cb=lambda feitos, total: prog(35 + feitos / total * 57, f"Gerando áudio {feitos}/{total}..."),
            cancelado=cancelado,
        )
        checar()

        prog(93, "Montando audiobook e capítulos...")
        partes = [
            (arquivos[valor] if tipo == "tts" else audio.silencio(tmp, valor), cap)
            for tipo, valor, cap in plano
        ]
        total, caps = audio.montar(partes, saida, op.formato, op.titulo, tmp)

    prog(100, "Concluído!")
    return Resultado(palavras, total, [{"titulo": c, "inicio": round(t, 1)} for c, t in caps], avisos)
