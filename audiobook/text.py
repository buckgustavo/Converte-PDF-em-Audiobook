"""Limpeza de texto e narração adaptada para livros técnicos."""

import re

# Marcadores usados pelo extrator para envolver código inline (fonte monoespaçada).
CODE_OPEN, CODE_CLOSE = "⟦", "⟧"

_LIGATURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "­": ""}

# ─────────────────────────────────────────
# PRONÚNCIA DE TERMOS TÉCNICOS
# Edite à vontade: a chave é o termo exatamente como aparece no texto.
# ─────────────────────────────────────────
PRONUNCIAS = {
    "pt": {
        "C++": "C mais mais", "C#": "C sharp", "F#": "F sharp", ".NET": "dot net",
        "Node.js": "Node JS", "Vue.js": "Vue JS", "Next.js": "Next JS",
        "JSON": "jêisson", "YAML": "iámel", "DRY": "drai", "YAGNI": "iágni",
        "GUI": "gúi", "SQL": "ésse quê éle", "NoSQL": "nô ésse quê éle",
        "Unix": "iúnix", "UNIX": "iúnix", "Linux": "línux",
        "I/O": "entrada e saída", "e.g.": "por exemplo", "i.e.": "isto é", "vs.": "versus",
        "README": "rid mi", "DevOps": "dev ops", "Wi-Fi": "uai fai",
    },
    "en": {
        "C++": "C plus plus", "C#": "C sharp", "F#": "F sharp", ".NET": "dot net",
        "Node.js": "Node JS", "Vue.js": "Vue JS", "Next.js": "Next JS",
        "JSON": "jason", "YAGNI": "yagni", "I/O": "I O",
        "e.g.": "for example", "i.e.": "that is", "vs.": "versus",
    },
    "es": {"C++": "C más más", "C#": "C sharp", ".NET": "dot net", "I/O": "entrada y salida"},
    "fr": {"C++": "C plus plus", "C#": "C sharp", ".NET": "dot net", "I/O": "entrée sortie"},
    "de": {"C++": "C plus plus", "C#": "C sharp", ".NET": "dot net", "I/O": "Ein- und Ausgabe"},
    "it": {"C++": "C più più", "C#": "C sharp", ".NET": "dot net", "I/O": "input output"},
}

_PRONUNCIAS_RE = {
    idioma: re.compile(
        r"(?<![\w.])("
        + "|".join(re.escape(k) for k in sorted(termos, key=len, reverse=True))
        + r")(?![\w+#])"
    )
    for idioma, termos in PRONUNCIAS.items()
}

_SIMBOLOS_CODIGO = {
    "pt": [("==", " é igual a "), ("!=", " diferente de "), ("<=", " menor ou igual a "),
           (">=", " maior ou igual a "), ("=>", " seta "), ("->", " seta "), ("&&", " e "),
           ("||", " ou "), ("=", " recebe "), ("+", " mais "), ("<", " menor que "), (">", " maior que ")],
    "en": [("==", " equals "), ("!=", " not equal "), ("<=", " less or equal "),
           (">=", " greater or equal "), ("=>", " arrow "), ("->", " arrow "), ("&&", " and "),
           ("||", " or "), ("=", " gets "), ("+", " plus "), ("<", " less than "), (">", " greater than ")],
}

_FRASES_CODIGO = {
    "pt": ("Exemplo de código", " em {}", "com uma linha", "com {} linhas"),
    "en": ("Code example", " in {}", "one line", "{} lines"),
    "es": ("Ejemplo de código", " en {}", "de una línea", "de {} líneas"),
    "fr": ("Exemple de code", " en {}", "une ligne", "{} lignes"),
    "de": ("Codebeispiel", " in {}", "eine Zeile", "{} Zeilen"),
    "it": ("Esempio di codice", " in {}", "di una riga", "di {} righe"),
}

_DESTAQUE_RE = re.compile(
    r"^(Tip|Dica|Note|Nota|Notice|Warning|Aviso|Atenção|Cuidado|Importante|Important|"
    r"Challenges?|Desafios?|Exercises?|Exercícios?|Consejo|Astuce|Tipp|Hinweis|Suggerimento)"
    r"(\s+\d+)?\s*(?:[:.—–-]\s*|\s+(?=[A-ZÀ-Ý])|$)"
)

_LINGUAGENS = [
    ("Elixir", r"\bdefmodule\b|\|>|\bdefp?\s+\w+.*\bdo\b"),
    ("Ruby", r"^\s*def\s+\w+[^:]*$|^\s*end\s*$|\bputs\b|\.each\s+do\b"),
    ("Python", r"^\s*def\s+\w+\(.*\)\s*:|^\s*(from\s+\w+\s+)?import\s+\w+|\bprint\(|\bself\b"),
    ("Rust", r"\bfn\s+\w+|\blet\s+mut\b|\bimpl\b"),
    ("Go", r"^\s*package\s+\w+|\bfunc\s+\w+|:="),
    ("Java", r"\bpublic\s+(static\s+)?(class|void|int|String)\b|System\.out"),
    ("C", r"#include\s*<|\bprintf\s*\("),
    ("JavaScript", r"\b(const|let|var)\s+\w+\s*=|\bfunction\b|=>|console\.log"),
    ("SQL", r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)\b"),
    ("HTML", r"<(html|div|p|span|body|head)\b"),
    ("terminal", r"^\s*[$%#]\s+\w+"),
]


def normalizar(texto):
    """Corrige ligaduras, hifenização de fim de linha, URLs, marcadores e espaços."""
    for lig, rep in _LIGATURAS.items():
        texto = texto.replace(lig, rep)
    # "pala-\nvra" -> "palavra" (só quando a continuação começa em minúscula)
    texto = re.sub(r"(\w)-\n\s*([a-zà-ÿ])", r"\1\2", texto)
    texto = re.sub(r"\s*\n\s*", " ", texto)
    texto = re.sub(r"(https?://|www\.)\S+", "", texto)
    texto = re.sub(r"[•►▶▸●◆■□▪→✓✔|]+", " ", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()


def falar_identificador(ident, idioma="pt"):
    """getUserName() -> get User Name, snake_case -> snake case, os.path -> os ponto path."""
    ident = re.sub(r"\(\s*\)", "", ident)
    ponto = " ponto " if idioma == "pt" else " dot "
    ident = re.sub(r"(?<=\w)\.(?=[A-Za-z_])", ponto, ident)
    ident = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ident)
    ident = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", ident)
    ident = re.sub(r"[_]+", " ", ident)
    ident = re.sub(r"[`{}\[\];]", " ", ident)
    return re.sub(r"\s{2,}", " ", ident).strip()


def aplicar_pronuncias(texto, idioma):
    regex = _PRONUNCIAS_RE.get(idioma)
    if not regex:
        return texto
    termos = PRONUNCIAS[idioma]
    return regex.sub(lambda m: termos[m.group(1)], texto)


def preparar_paragrafo(texto, idioma="pt", modo_tecnico=True):
    texto = normalizar(texto)
    if not modo_tecnico:
        return texto.replace(CODE_OPEN, "").replace(CODE_CLOSE, "")

    texto = aplicar_pronuncias(texto, idioma)
    texto = re.sub(
        re.escape(CODE_OPEN) + r"(.*?)" + re.escape(CODE_CLOSE),
        lambda m: falar_identificador(m.group(1), idioma),
        texto,
    )
    texto = texto.replace(CODE_OPEN, "").replace(CODE_CLOSE, "")
    # Identificadores soltos no texto: camelCase e snake_case
    texto = re.sub(r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b", lambda m: falar_identificador(m.group(0), idioma), texto)
    texto = re.sub(r"\b[A-Za-z]+(?:_[A-Za-z0-9]+)+\b", lambda m: falar_identificador(m.group(0), idioma), texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def destaque(paragrafo):
    """Se o parágrafo é uma dica/nota/aviso, devolve o texto com pausa após o rótulo."""
    m = _DESTAQUE_RE.match(paragrafo)
    if not m:
        return None
    rotulo = (m.group(1) + (m.group(2) or "")).strip()
    resto = paragrafo[m.end():].strip()
    return f"{rotulo}. {resto}" if resto else f"{rotulo}."


def detectar_linguagem(codigo):
    for nome, padrao in _LINGUAGENS:
        if re.search(padrao, codigo, re.MULTILINE):
            return nome
    return None


def narrar_codigo(codigo, idioma="pt", modo="anunciar"):
    """modo: 'omitir' -> None | 'anunciar' -> frase curta | 'ler' -> anúncio + leitura linha a linha."""
    if modo == "omitir":
        return None
    linhas = [l for l in codigo.splitlines() if l.strip()]
    if not linhas:
        return None

    base, em, uma, varias = _FRASES_CODIGO.get(idioma, _FRASES_CODIGO["en"])
    linguagem = detectar_linguagem(codigo)
    tamanho = uma if len(linhas) == 1 else varias.format(len(linhas))
    anuncio = base + (em.format(linguagem) if linguagem else "")

    if modo != "ler":
        return f"{anuncio}, {tamanho}."

    simbolos = _SIMBOLOS_CODIGO.get(idioma, _SIMBOLOS_CODIGO["en"])
    falas = []
    for linha in linhas:
        linha = linha.strip().lstrip("$%>").strip()
        linha = re.sub(r"^(#|//|--|/\*|\*)\s*", "", linha)
        for simbolo, fala in simbolos:
            linha = linha.replace(simbolo, fala)
        linha = re.sub(r"[\"'`]", "", linha)
        linha = re.sub(r"[A-Za-z_][\w.]*\w(\(\))?", lambda m: falar_identificador(m.group(0), idioma), linha)
        linha = re.sub(r"[{}()\[\];,:\\]", " ", linha)
        linha = re.sub(r"\s{2,}", " ", linha).strip()
        if linha:
            falas.append(linha.rstrip(".") + ".")
    return f"{anuncio}: " + " ".join(falas) if falas else f"{anuncio}, {tamanho}."


def dividir_texto(texto, tamanho=1800):
    """Divide em pedaços de até `tamanho` caracteres sem cortar frases (ou palavras)."""
    frases = re.split(r"(?<=[.!?…])\s+", texto.strip())
    pedacos, atual = [], ""

    def quebrar(frase):
        while len(frase) > tamanho:
            corte = max(frase.rfind(s, 0, tamanho) for s in (";", ":", ",", " "))
            corte = corte if corte > tamanho // 3 else tamanho
            yield frase[: corte + 1].strip()
            frase = frase[corte + 1 :].strip()
        if frase:
            yield frase

    for frase in frases:
        for parte in quebrar(frase):
            if atual and len(atual) + 1 + len(parte) > tamanho:
                pedacos.append(atual)
                atual = parte
            else:
                atual = f"{atual} {parte}" if atual else parte
    if atual:
        pedacos.append(atual)
    return pedacos
