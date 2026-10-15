"""Catálogo de vozes neurais do Edge TTS usadas pela aplicação."""

IDIOMAS = {
    "pt": {"nome": "Português", "ocr": "por"},
    "en": {"nome": "Inglês", "ocr": "eng"},
    "es": {"nome": "Espanhol", "ocr": "spa"},
    "fr": {"nome": "Francês", "ocr": "fra"},
    "de": {"nome": "Alemão", "ocr": "deu"},
    "it": {"nome": "Italiano", "ocr": "ita"},
}

# (voz, idioma, região, gênero)
VOZES = [
    ("pt-BR-AntonioNeural", "pt", "Brasil", "M"),
    ("pt-BR-FranciscaNeural", "pt", "Brasil", "F"),
    ("pt-PT-DuarteNeural", "pt", "Portugal", "M"),
    ("pt-PT-RaquelNeural", "pt", "Portugal", "F"),
    ("en-US-AndrewNeural", "en", "EUA", "M"),
    ("en-US-AriaNeural", "en", "EUA", "F"),
    ("en-US-GuyNeural", "en", "EUA", "M"),
    ("en-US-JennyNeural", "en", "EUA", "F"),
    ("en-GB-RyanNeural", "en", "Reino Unido", "M"),
    ("en-GB-SoniaNeural", "en", "Reino Unido", "F"),
    ("en-AU-WilliamNeural", "en", "Austrália", "M"),
    ("en-AU-NatashaNeural", "en", "Austrália", "F"),
    ("es-ES-AlvaroNeural", "es", "Espanha", "M"),
    ("es-ES-ElviraNeural", "es", "Espanha", "F"),
    ("es-MX-JorgeNeural", "es", "México", "M"),
    ("es-MX-DaliaNeural", "es", "México", "F"),
    ("fr-FR-HenriNeural", "fr", "França", "M"),
    ("fr-FR-DeniseNeural", "fr", "França", "F"),
    ("de-DE-ConradNeural", "de", "Alemanha", "M"),
    ("de-DE-KatjaNeural", "de", "Alemanha", "F"),
    ("it-IT-DiegoNeural", "it", "Itália", "M"),
    ("it-IT-ElsaNeural", "it", "Itália", "F"),
]

_POR_NOME = {v[0]: v for v in VOZES}

VOZ_PADRAO = {idioma: next(v[0] for v in VOZES if v[1] == idioma) for idioma in IDIOMAS}

AMOSTRAS = {
    "pt": "Olá! Esta é uma prévia da voz que vai narrar o seu audiobook.",
    "en": "Hello! This is a preview of the voice that will narrate your audiobook.",
    "es": "¡Hola! Esta es una muestra de la voz que narrará tu audiolibro.",
    "fr": "Bonjour ! Voici un aperçu de la voix qui lira votre livre audio.",
    "de": "Hallo! Dies ist eine Vorschau der Stimme, die Ihr Hörbuch vorliest.",
    "it": "Ciao! Questa è un'anteprima della voce che leggerà il tuo audiolibro.",
}


def listar_vozes():
    return [
        {"id": nome, "idioma": idioma, "regiao": regiao, "genero": genero}
        for nome, idioma, regiao, genero in VOZES
    ]


def voz_valida(voz):
    return voz in _POR_NOME


def idioma_da_voz(voz):
    return _POR_NOME[voz][1] if voz in _POR_NOME else voz.split("-")[0]


def voz_alternativa(voz):
    """Voz do gênero oposto na mesma região — usada para títulos, dicas e código."""
    if voz not in _POR_NOME:
        return voz
    _, idioma, regiao, genero = _POR_NOME[voz]
    for nome, i, r, g in VOZES:
        if i == idioma and r == regiao and g != genero:
            return nome
    return voz
