"""Extração estruturada de PDFs (títulos, parágrafos, código) com PyMuPDF + OCR por página."""

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from .text import CODE_CLOSE, CODE_OPEN

MARGEM = 0.07          # faixa superior/inferior da página onde vivem cabeçalhos e rodapés
MIN_PALAVRAS_OCR = 10  # páginas com menos palavras que isso são tratadas como escaneadas
_MONO_RE = re.compile(r"mono|courier|consol|menlo|code|inconsolata|fira ?code|source ?code|dejavu ?sans ?m", re.I)


@dataclass
class Bloco:
    tipo: str   # "titulo" | "texto" | "codigo"
    texto: str
    pagina: int
    nivel: int = 0
    capitulo: str | None = None  # preenchido no bloco que inicia um capítulo


@dataclass
class _Linha:
    texto: str
    tamanho: float
    mono: bool
    y0: float
    y1: float
    bloco: int


def _eh_mono(span):
    return bool(span["flags"] & 8) or bool(_MONO_RE.search(span["font"]))


def _linhas_da_pagina(page):
    linhas = []
    dados = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP)
    for b_idx, bloco in enumerate(dados["blocks"]):
        if bloco.get("type") != 0:
            continue
        for linha in bloco["lines"]:
            spans = [s for s in linha["spans"] if s["text"].strip()]
            if not spans:
                continue
            chars = sum(len(s["text"]) for s in spans)
            mono_chars = sum(len(s["text"]) for s in spans if _eh_mono(s))
            todo_mono = mono_chars / chars > 0.8
            if todo_mono:
                texto = "".join(s["text"] for s in linha["spans"]).rstrip()
            else:
                partes = []
                for s in linha["spans"]:
                    if _eh_mono(s) and s["text"].strip():
                        partes.append(f"{CODE_OPEN}{s['text'].strip()}{CODE_CLOSE} ")
                    else:
                        partes.append(s["text"])
                texto = "".join(partes).strip()
            tamanho = max(s["size"] for s in spans)
            linhas.append(_Linha(texto, round(tamanho, 1), todo_mono, linha["bbox"][1], linha["bbox"][3], b_idx))
    return linhas


def _chave_margem(texto):
    return re.sub(r"\d+", "#", texto.lower()).strip()


def _ocr_pagina(page, lang):
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(img, lang=lang)


def _tesseract_disponivel():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extrair(caminho_pdf, idioma_ocr="por", pagina_inicio=None, pagina_fim=None, progress_cb=None, cancelado=None):
    """Devolve (blocos, avisos). Páginas são 1-indexadas e inclusivas."""
    avisos = []
    doc = pymupdf.open(caminho_pdf)
    try:
        total = doc.page_count
        inicio = max(1, pagina_inicio or 1)
        fim = min(total, pagina_fim or total)
        if inicio > fim:
            raise ValueError(f"Intervalo de páginas inválido (o PDF tem {total} páginas).")

        # 1ª passada: linhas de cada página (+ OCR quando a página não tem texto)
        paginas = {}
        ocr = {}
        tesseract_ok = None
        for n in range(inicio, fim + 1):
            if cancelado and cancelado():
                raise InterruptedError
            page = doc[n - 1]
            linhas = _linhas_da_pagina(page)
            if sum(len(l.texto.split()) for l in linhas) < MIN_PALAVRAS_OCR and page.get_images():
                if tesseract_ok is None:
                    tesseract_ok = _tesseract_disponivel()
                    if not tesseract_ok:
                        avisos.append("Páginas escaneadas encontradas, mas o Tesseract (OCR) não está instalado.")
                if tesseract_ok:
                    try:
                        ocr[n] = _ocr_pagina(page, idioma_ocr)
                        linhas = []
                    except Exception as e:
                        avisos.append(f"OCR falhou na página {n}: {e}")
            paginas[n] = (linhas, page.rect.height)
            if progress_cb:
                modo = "OCR" if n in ocr else "Lendo"
                progress_cb(int((n - inicio + 1) / (fim - inicio + 1) * 100), f"{modo} página {n}/{fim}...")

        # Tamanho de fonte do corpo = o mais frequente (ponderado por caracteres)
        freq = Counter()
        for linhas, _ in paginas.values():
            for l in linhas:
                if not l.mono:
                    freq[l.tamanho] += len(l.texto)
        corpo = freq.most_common(1)[0][0] if freq else 10.0
        tamanhos_titulo = sorted({t for t in freq if t >= corpo * 1.2}, reverse=True)

        # Cabeçalhos/rodapés repetidos (título do livro, número de página...)
        repetidos = Counter()
        for linhas, altura in paginas.values():
            for chave in {_chave_margem(l.texto) for l in linhas if _na_margem(l, altura)}:
                repetidos[chave] += 1
        limite_rep = max(3, int(len(paginas) * 0.2))

        def descartar(l, altura):
            if not _na_margem(l, altura):
                return False
            chave = _chave_margem(l.texto)
            return repetidos[chave] >= limite_rep or re.fullmatch(r"[#ivxlc\s.\-–—]*", chave) is not None

        blocos = []
        for n, (linhas, altura) in paginas.items():
            if n in ocr:
                for par in re.split(r"\n\s*\n", ocr[n]):
                    if par.strip():
                        blocos.append(Bloco("texto", par.strip(), n))
                continue
            linhas = [l for l in linhas if not descartar(l, altura)]
            _agrupar(linhas, n, corpo, tamanhos_titulo, blocos)

        _marcar_capitulos(doc.get_toc(simple=True), blocos, inicio, fim)
        return _juntar_paragrafos_quebrados(blocos), avisos
    finally:
        doc.close()


def _na_margem(linha, altura):
    return linha.y1 < altura * MARGEM or linha.y0 > altura * (1 - MARGEM)


def _agrupar(linhas, pagina, corpo, tamanhos_titulo, blocos):
    atual, atual_bloco = None, None
    for l in linhas:
        if l.mono:
            tipo, nivel = "codigo", 0
        elif l.tamanho >= corpo * 1.2 and 2 < len(l.texto.strip()) < 150:
            tipo, nivel = "titulo", tamanhos_titulo.index(l.tamanho) + 1 if l.tamanho in tamanhos_titulo else 1
        else:
            tipo, nivel = "texto", 0

        mesmo = atual and atual.tipo == tipo and (tipo == "codigo" or atual_bloco == l.bloco)
        if mesmo:
            sep = "\n" if tipo in ("codigo", "texto") else " "
            atual.texto += sep + l.texto
        else:
            atual = Bloco(tipo, l.texto, pagina, nivel)
            atual_bloco = l.bloco
            blocos.append(atual)


def _juntar_paragrafos_quebrados(blocos):
    """Une parágrafos de texto partidos pela virada de página."""
    resultado = []
    for b in blocos:
        ant = resultado[-1] if resultado else None
        if (
            ant and ant.tipo == b.tipo == "texto" and b.capitulo is None
            and b.pagina == ant.pagina + 1
            and not re.search(r"[.!?:…\"”)]\s*$", ant.texto)
            and re.match(r"[a-zà-ÿ]", b.texto)
        ):
            ant.texto += "\n" + b.texto
        else:
            resultado.append(b)
    return resultado


def _marcar_capitulos(toc, blocos, inicio, fim):
    """Usa o sumário (marcadores) do PDF; sem sumário, usa os títulos de maior nível."""
    if not blocos:
        return
    entradas = [(nivel, titulo.strip(), pag) for nivel, titulo, pag in toc if inicio <= pag <= fim and titulo.strip()]
    if entradas:
        nivel_cap = min(n for n, _, _ in entradas)
        # Se o nível de topo tiver só 1–2 entradas (ex.: "Parte I"), desce um nível
        if sum(1 for n, _, _ in entradas if n == nivel_cap) <= 2 and any(n == nivel_cap + 1 for n, _, _ in entradas):
            nivel_cap += 1
        for _, titulo, pag in (e for e in entradas if e[0] <= nivel_cap):
            alvo = _achar_bloco(blocos, titulo, pag)
            if alvo and alvo.capitulo is None:
                alvo.capitulo = titulo
    else:
        titulos = [b for b in blocos if b.tipo == "titulo"]
        if titulos:
            topo = min(b.nivel for b in titulos)
            for b in titulos:
                if b.nivel == topo:
                    b.capitulo = re.sub(r"\s+", " ", b.texto).strip()

    if blocos[0].capitulo is None:
        blocos[0].capitulo = "Início"


def _achar_bloco(blocos, titulo, pagina):
    norm = lambda s: re.sub(r"\W+", "", s.lower())
    alvo = norm(titulo)[:30]
    da_pagina = [b for b in blocos if b.pagina == pagina]
    for b in da_pagina:
        if b.tipo == "titulo" and alvo and alvo in norm(b.texto):
            return b
    for b in blocos:
        if b.pagina >= pagina:
            return b
    return None
