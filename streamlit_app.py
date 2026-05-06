import os
import tempfile

import streamlit as st

from core import gerar_audio

st.set_page_config(page_title="PDF para Audiobook", layout="centered")
st.title("PDF para Audiobook")
st.caption("Voz neural Edge TTS — sem limite de tamanho")

SOTAQUES = {
    "pt": {"Brasil (pt-BR)": "com.br", "Portugal (pt-PT)": "com"},
    "en": {"EUA (en-US)": "com", "Reino Unido (en-GB)": "co.uk", "Austrália (en-AU)": "com.au"},
    "es": {"Espanha (es-ES)": "com", "México (es-MX)": "com.br"},
    "fr": {"França (fr-FR)": "com"},
    "de": {"Alemanha (de-DE)": "com"},
}

IDIOMA_LABEL = {"pt": "Português", "en": "Inglês", "es": "Espanhol", "fr": "Francês", "de": "Alemão"}


def auto_chunk(size_bytes):
    if size_bytes < 204800:   return 1000
    if size_bytes < 1048576:  return 1400
    if size_bytes < 5242880:  return 1800
    if size_bytes < 20971520: return 2200
    return 2500


if "chunk_size" not in st.session_state:
    st.session_state.chunk_size = 1800

arquivo = st.file_uploader("Selecione o PDF", type=["pdf"])

if arquivo and st.session_state.get("_last_file") != arquivo.name:
    st.session_state.chunk_size = auto_chunk(arquivo.size)
    st.session_state["_last_file"] = arquivo.name

with st.sidebar:
    st.header("Configurações")
    idioma = st.selectbox("Idioma", list(SOTAQUES.keys()), format_func=lambda x: IDIOMA_LABEL[x])
    sotaque_opts = SOTAQUES[idioma]
    sotaque_label = st.selectbox("Sotaque / Voz", list(sotaque_opts.keys()))
    sotaque = sotaque_opts[sotaque_label]
    velocidade_lenta = st.checkbox("Leitura lenta")
    remover_codigo = st.checkbox("Remover código", value=True)
    chunk_size = st.slider("Tamanho do chunk (chars)", 800, 2500, step=100, key="chunk_size")

if arquivo:
    col1, col2 = st.columns([3, 1])
    col1.success(arquivo.name)
    col2.metric("Tamanho", f"{arquivo.size / 1024:.0f} KB")

    if st.button("Converter para MP3", type="primary", use_container_width=True):
        barra = st.progress(0)
        status = st.empty()

        def prog(pct, msg):
            barra.progress(pct / 100)
            status.text(msg)

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "entrada.pdf")
            mp3_path = os.path.join(tmp, "saida.mp3")

            with open(pdf_path, "wb") as f:
                f.write(arquivo.read())

            try:
                word_count = gerar_audio(
                    pdf_path, mp3_path,
                    idioma=idioma,
                    sotaque=sotaque,
                    velocidade_lenta=velocidade_lenta,
                    chunk_size=chunk_size,
                    remover_codigo=remover_codigo,
                    progress_cb=prog,
                )
                with open(mp3_path, "rb") as f:
                    dados = f.read()
            except Exception as e:
                st.error(str(e))
                st.stop()

        barra.progress(1.0)
        status.empty()
        st.success(f"{word_count:,} palavras convertidas")
        st.audio(dados, format="audio/mp3")
        st.download_button(
            "Baixar MP3",
            dados,
            arquivo.name.replace(".pdf", ".mp3"),
            "audio/mpeg",
            use_container_width=True,
        )
