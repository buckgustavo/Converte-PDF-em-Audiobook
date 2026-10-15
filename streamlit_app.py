"""Interface alternativa em Streamlit (opcional): pip install streamlit && streamlit run streamlit_app.py"""

import os
import tempfile
from pathlib import Path

import streamlit as st

from audiobook import Opcoes, gerar_audiobook
from audiobook.voices import IDIOMAS, VOZ_PADRAO, listar_vozes

st.set_page_config(page_title="PDF para Audiobook", layout="centered")
st.title("PDF para Audiobook")
st.caption("Voz neural Edge TTS — com capítulos e modo livro técnico")

arquivo = st.file_uploader("Selecione o PDF", type=["pdf"])

with st.sidebar:
    st.header("Configurações")
    idioma = st.selectbox("Idioma", list(IDIOMAS), format_func=lambda x: IDIOMAS[x]["nome"])
    vozes = [v for v in listar_vozes() if v["idioma"] == idioma]
    ids = [v["id"] for v in vozes]
    voz = st.selectbox(
        "Voz", ids, index=ids.index(VOZ_PADRAO[idioma]),
        format_func=lambda i: next(f"{i.split('-')[2][:-6]} — {v['regiao']}" for v in vozes if v["id"] == i),
    )
    velocidade = st.slider("Velocidade (%)", -50, 50, 0, step=5)
    modo_tecnico = st.checkbox("Modo livro técnico", value=True)
    codigo = st.radio("Blocos de código", ["anunciar", "omitir", "ler"], horizontal=True)
    voz_destaque = st.checkbox("Segunda voz em títulos e dicas", value=True)
    formato = st.radio("Formato", ["mp3", "m4b"], horizontal=True)

if arquivo and st.button("Converter", type="primary", use_container_width=True):
    barra = st.progress(0)
    status = st.empty()

    def prog(pct, msg):
        barra.progress(pct / 100)
        status.text(msg)

    nome = Path(arquivo.name).stem
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "entrada.pdf")
        saida = os.path.join(tmp, f"saida.{formato}")
        with open(pdf_path, "wb") as f:
            f.write(arquivo.read())
        try:
            r = gerar_audiobook(pdf_path, saida, Opcoes(
                voz=voz, velocidade=velocidade, modo_tecnico=modo_tecnico, codigo=codigo,
                voz_destaque=voz_destaque, formato=formato, titulo=nome,
            ), progress_cb=prog)
            with open(saida, "rb") as f:
                dados = f.read()
        except Exception as e:
            st.error(str(e))
            st.stop()

    status.empty()
    st.success(f"{r.palavras:,} palavras · {len(r.capitulos)} capítulos")
    for aviso in r.avisos:
        st.warning(aviso)
    mime = "audio/mp4" if formato == "m4b" else "audio/mpeg"
    st.audio(dados, format=mime)
    st.download_button(f"Baixar {formato.upper()}", dados, f"{nome}.{formato}", mime, use_container_width=True)
