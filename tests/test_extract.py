from audiobook import extract
from audiobook.pipeline import Opcoes, montar_roteiro


def test_extrai_estrutura(pdf_tecnico):
    blocos, avisos = extract.extrair(pdf_tecnico)
    tipos = [b.tipo for b in blocos]
    assert avisos == []
    assert tipos.count("titulo") == 2
    assert tipos.count("codigo") == 1
    codigo = next(b for b in blocos if b.tipo == "codigo")
    assert "def saudacao(nome):" in codigo.texto
    assert codigo.texto.count("\n") == 2


def test_remove_rodape_repetido(pdf_tecnico):
    blocos, _ = extract.extrair(pdf_tecnico)
    assert not any("O Programador Pragmático" in b.texto for b in blocos)


def test_capitulos_vem_do_sumario(pdf_tecnico):
    blocos, _ = extract.extrair(pdf_tecnico)
    caps = [b.capitulo for b in blocos if b.capitulo]
    assert caps == ["Capítulo 1 — Uma Filosofia Pragmática", "Capítulo 2 — Uma Abordagem Pragmática"]


def test_intervalo_de_paginas(pdf_tecnico):
    blocos, _ = extract.extrair(pdf_tecnico, pagina_inicio=3, pagina_fim=4)
    assert {b.pagina for b in blocos} == {3, 4}
    assert [b.capitulo for b in blocos if b.capitulo] == ["Capítulo 2 — Uma Abordagem Pragmática"]


def test_roteiro_tecnico(pdf_tecnico):
    blocos, _ = extract.extrair(pdf_tecnico)
    roteiro = montar_roteiro(blocos, Opcoes())
    textos = [s.texto for s in roteiro]
    assert "Dica 1. Cuide do seu ofício." in textos
    assert "Exemplo de código em Python, com 3 linhas." in textos
    assert any("get User Name" in t for t in textos)
    assert sum(1 for s in roteiro if s.capitulo) == 2
    assert all(s.destaque for s in roteiro if s.texto.startswith(("Dica", "Tip", "Exemplo")))


def test_roteiro_omitindo_codigo(pdf_tecnico):
    blocos, _ = extract.extrair(pdf_tecnico)
    roteiro = montar_roteiro(blocos, Opcoes(codigo="omitir"))
    assert not any("código" in s.texto.lower() and "Exemplo" in s.texto for s in roteiro)


def test_opcoes_saneadas():
    op = Opcoes(voz="en-GB-RyanNeural", velocidade=999, chunk_size=10, codigo="x", formato="wav")
    assert op.idioma == "en"
    assert (op.velocidade, op.chunk_size, op.codigo, op.formato) == (100, 300, "anunciar", "mp3")
    assert Opcoes(idioma="xx").voz == "pt-BR-AntonioNeural"


def test_pagina_escaneada_sem_tesseract_gera_aviso(tmp_path, monkeypatch):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    page.insert_image(page.rect, pixmap=pix)
    caminho = tmp_path / "scan.pdf"
    doc.save(caminho)

    monkeypatch.setattr(extract, "_tesseract_disponivel", lambda: False)
    blocos, avisos = extract.extrair(str(caminho))
    assert blocos == []
    assert any("Tesseract" in a for a in avisos)
