import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CORPO = (
    "Programadores pragmáticos cuidam do seu ofício. Não faz sentido desenvolver software "
    "a menos que você se importe em fazê-lo bem. Para isso usamos a função getUserName "
    "e também a variável max_retries em vários exemplos deste capítulo."
)


def _pagina(doc, titulo=None, paragrafos=(), codigo=None, rodape="O Programador Pragmático"):
    page = doc.new_page()
    y = 72
    if titulo:
        page.insert_text((72, y), titulo, fontsize=20, fontname="hebo")
        y += 40
    for par in paragrafos:
        caixa = pymupdf.Rect(72, y, 520, y + 120)
        page.insert_textbox(caixa, par, fontsize=11, fontname="helv")
        y += 130
    if codigo:
        for linha in codigo.splitlines():
            page.insert_text((90, y), linha, fontsize=10, fontname="cour")
            y += 13
    page.insert_text((72, 820), f"{rodape}  {doc.page_count}", fontsize=8, fontname="helv")
    return page


@pytest.fixture
def pdf_tecnico(tmp_path):
    doc = pymupdf.open()
    _pagina(doc, "Capítulo 1 — Uma Filosofia Pragmática", [CORPO, "Dica 1: Cuide do seu ofício."])
    _pagina(doc, None, [CORPO], codigo='def saudacao(nome):\n    print("Olá", nome)\n    return nome')
    _pagina(doc, "Capítulo 2 — Uma Abordagem Pragmática", [CORPO, "Tip 14 Good Design Is Easier to Change"])
    _pagina(doc, None, [CORPO])
    doc.set_toc([[1, "Capítulo 1 — Uma Filosofia Pragmática", 1], [1, "Capítulo 2 — Uma Abordagem Pragmática", 3]])
    caminho = tmp_path / "livro.pdf"
    doc.save(caminho)
    return str(caminho)
