import os
import re
import time
import tempfile
import asyncio
import streamlit as st
import PyPDF2
import pytesseract
import edge_tts
from pdf2image import convert_from_path
from PIL import Image

# ─────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PDF para Audiobook (Edge TTS)",
    page_icon="🎧",
    layout="centered"
)

st.title("🎧 PDF para Audiobook")
st.markdown("**Edge TTS** — Voz neural da Microsoft, grátis e de alta qualidade!")

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurações")
    idioma = st.selectbox("Idioma", ["pt", "en", "es"], index=0)
    vozes = {
        "pt": ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"],
        "en": ["en-US-AriaNeural", "en-US-JennyNeural"],
        "es": ["es-ES-AlvaroNeural", "es-ES-ElviraNeural"]
    }
    voz_idx = st.slider("Voz", 0, len(vozes[idioma]) - 1, 0)
    voz_selecionada = vozes[idioma][voz_idx]
    
    velocidade_lenta = st.checkbox("Mais lenta", value=False)
    chunk_size = st.slider("Chunk (chars)", 800, 2500, 1500, 100)
    remover_codigo = st.checkbox("Remover código", value=True)

# ─────────────────────────────────────────
# FUNÇÕES DE EXTRAÇÃO
# ─────────────────────────────────────────

@st.cache_data
def extrair_texto_digital(caminho_pdf):
    texto = ""
    with open(caminho_pdf, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)
        bar = st.progress(0)
        for i, page in enumerate(reader.pages):
            t = page.extract_text()
            if t:
                texto += t + " "
            bar.progress((i + 1) / total)
    return texto.strip()

def extrair_texto_ocr(caminho_pdf):
    st.info("📷 Usando OCR...")
    paginas = convert_from_path(caminho_pdf, dpi=250)
    texto = ""
    bar = st.progress(0)
    lang_ocr = 'por' if idioma == 'pt' else 'eng'
    for i, pagina in enumerate(paginas):
        pagina_cinza = pagina.convert('L')
        t = pytesseract.image_to_string(pagina_cinza, lang=lang_ocr)
        texto += t + " "
        bar.progress((i + 1) / len(paginas))
    return texto.strip()

def extrair_texto(caminho_pdf):
    texto = extrair_texto_digital(caminho_pdf)
    if len(texto.split()) < 50:
        texto = extrair_texto_ocr(caminho_pdf)
    return texto

# ─────────────────────────────────────────
# LIMPEZA DE TEXTO
# ─────────────────────────────────────────

def limpar_texto(texto):
    linhas = [l for l in texto.split('\n') if len(l.strip()) > 40]
    texto = '\n'.join(linhas)
    
    if remover_codigo:
        padroes_codigo = [
            r'^\s*(def |class |import |from |return |if |else:|for |while)',
            r'^\s*[{}();]+\s*$',
            r'^\s*#',
        ]
        linhas_filtradas = []
        for linha in texto.split('\n'):
            if not any(re.match(p, linha) for p in padroes_codigo):
                linhas_filtradas.append(linha)
        texto = '\n'.join(linhas_filtradas)
    
    texto = re.sub(r'http\S+', '', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = re.sub(r' {2,}', ' ', texto)
    
    return texto.strip()

# ─────────────────────────────────────────
# EDGE TTS — GERAÇÃO DE ÁUDIO
# ─────────────────────────────────────────

async def gerar_audio_edge(chunks, pasta_tmp):
    arquivos = [None] * len(chunks)
    bar = st.progress(0, text="Gerando áudio...")
    semaforo = asyncio.Semaphore(10)  # 10 requisições simultâneas

    async def processar_chunk(i, chunk):
        async with semaforo:
            caminho = os.path.join(pasta_tmp, f"parte_{i+1:04d}.mp3")
            try:
                communicate = edge_tts.Communicate(
                    chunk,
                    voz_selecionada,
                    rate='-10%' if not velocidade_lenta else '-20%'
                )
                await communicate.save(caminho)
                arquivos[i] = caminho
            except Exception as e:
                st.warning(f"Erro parte {i+1}: {e}")
            bar.progress((sum(1 for x in arquivos if x) ) / len(chunks))

    await asyncio.gather(*[processar_chunk(i, chunk) for i, chunk in enumerate(chunks)])
    return [a for a in arquivos if a]

# ─────────────────────────────────────────
# JUNÇÃO MP3
# ─────────────────────────────────────────

def juntar_mp3(arquivos):
    from pydub import AudioSegment
    audio_final = AudioSegment.empty()
    for arq in arquivos:
        audio_final += AudioSegment.from_mp3(arq)
    buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    audio_final.export(buffer.name, format="mp3")
    return buffer.name

# ─────────────────────────────────────────
# INTERFACE PRINCIPAL
# ─────────────────────────────────────────

arquivo = st.file_uploader("📂 Upload PDF", type=["pdf"])

if arquivo:
    st.success(f"{arquivo.name}")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"**Voz:** {voz_selecionada}")
    with col2:
        st.metric("Tamanho", f"{arquivo.size/1024:.0f} KB")
    
    if st.button("🚀 Converter!", type="primary", use_container_width=True):
        with tempfile.TemporaryDirectory() as pasta_tmp:
            # Salva PDF
            caminho_pdf = os.path.join(pasta_tmp, "livro.pdf")
            with open(caminho_pdf, 'wb') as f:
                f.write(arquivo.read())
            
            with st.spinner("Processando..."):
                # Extrai texto
                texto = extrair_texto(caminho_pdf)
                texto = limpar_texto(texto)
                
                st.success(f"📝 **{len(texto.split()):,} palavras** extraídas")
                
                # Divide chunks
                chunks = []
                for t in texto.split('\n\n'):
                    if len(t) > 50:
                        chunks.append(t.strip())
                
                st.info(f"🎤 **{len(chunks)} partes** de áudio")
                
                # GERA ÁUDIO com Edge TTS
                arquivos_audio = asyncio.run(gerar_audio_edge(chunks, pasta_tmp))
                
                if arquivos_audio:
                    # Junta MP3s
                    mp3_final = juntar_mp3(arquivos_audio)
                    
                    # Download
                    with open(mp3_final, 'rb') as f:
                        dados_mp3 = f.read()
                    
                    nome_saida = arquivo.name.replace('.pdf', '_edge_tts.mp3')
                    
                    st.audio(dados_mp3)
                    st.download_button(
                        label="⬇Baixar MP3",
                        data=dados_mp3,
                        file_name=nome_saida,
                        mime="audio/mpeg"
                    )
                else:
                    st.error("❌ Erro na geração de áudio")