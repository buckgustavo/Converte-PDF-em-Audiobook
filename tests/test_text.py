from audiobook.text import (
    CODE_CLOSE, CODE_OPEN, destaque, detectar_linguagem, dividir_texto,
    falar_identificador, narrar_codigo, normalizar, preparar_paragrafo,
)


def test_normalizar_junta_hifenizacao_e_linhas():
    assert normalizar("progra-\nmação pragmática\ncontinua") == "programação pragmática continua"


def test_normalizar_mantem_hifen_de_palavra_composta():
    assert normalizar("guarda-\nChuva") == "guarda- Chuva"
    assert normalizar("fazê-lo bem") == "fazê-lo bem"


def test_normalizar_remove_urls_e_marcadores():
    assert normalizar("• veja https://exemplo.com/x agora") == "veja agora"


def test_linhas_curtas_nao_sao_descartadas():
    # A versão antiga removia toda linha com menos de 40 caracteres
    assert preparar_paragrafo("Fim.") == "Fim."


def test_falar_identificador():
    assert falar_identificador("getUserName()") == "get User Name"
    assert falar_identificador("max_retries") == "max retries"
    assert falar_identificador("os.path", "pt") == "os ponto path"
    assert falar_identificador("HTTPServer") == "HTTP Server"


def test_preparar_paragrafo_modo_tecnico():
    t = preparar_paragrafo(f"Chame {CODE_OPEN}parseConfig(){CODE_CLOSE} e leia o JSON em C++.", "pt")
    assert "parse Config" in t
    assert "jêisson" in t
    assert "C mais mais" in t
    assert CODE_OPEN not in t


def test_preparar_paragrafo_sem_modo_tecnico_so_remove_marcadores():
    t = preparar_paragrafo(f"Use {CODE_OPEN}getX{CODE_CLOSE} com JSON.", "pt", modo_tecnico=False)
    assert t == "Use getX com JSON."


def test_frases_comuns_em_ingles_nao_sao_tratadas_como_codigo():
    t = preparar_paragrafo("for each item in the list, import the data from the file", "en")
    assert t == "for each item in the list, import the data from the file"


def test_destaque_dicas():
    assert destaque("Dica 1: Cuide do seu ofício.") == "Dica 1. Cuide do seu ofício."
    assert destaque("Tip 14 Good Design Is Easier to Change") == "Tip 14. Good Design Is Easier to Change"
    assert destaque("Nota: isto é importante") == "Nota. isto é importante"
    assert destaque("Notável é o trabalho") is None
    assert destaque("Dicas são úteis") is None


def test_detectar_linguagem():
    assert detectar_linguagem("def soma(a, b):\n    return a + b") == "Python"
    assert detectar_linguagem("defmodule Foo do\n  def bar, do: 1\nend") == "Elixir"
    assert detectar_linguagem("def hello\n  puts 'oi'\nend") == "Ruby"
    assert detectar_linguagem("const x = () => 1;") == "JavaScript"
    assert detectar_linguagem("$ git commit -m 'x'") == "terminal"


def test_narrar_codigo_modos():
    codigo = "def soma(a, b):\n    return a + b"
    assert narrar_codigo(codigo, "pt", "omitir") is None
    assert narrar_codigo(codigo, "pt", "anunciar") == "Exemplo de código em Python, com 2 linhas."
    lido = narrar_codigo(codigo, "pt", "ler")
    assert lido.startswith("Exemplo de código em Python:")
    assert "return a mais b" in lido


def test_dividir_texto_respeita_tamanho_e_nao_corta_palavras():
    texto = " ".join(f"Frase número {i} com algumas palavras." for i in range(200))
    pedacos = dividir_texto(texto, 300)
    assert all(len(p) <= 300 for p in pedacos)
    assert " ".join(pedacos) == texto


def test_dividir_texto_frase_gigante_sem_pontuacao():
    texto = "palavra " * 500
    pedacos = dividir_texto(texto.strip(), 200)
    assert all(len(p) <= 200 for p in pedacos)
    assert all(not p.startswith("alavra") for p in pedacos)
    assert " ".join(pedacos).split() == texto.split()
