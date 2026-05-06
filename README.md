# 📖➡️🎧 PDF para Audiobook

Cansado de ferramentas online ruins, lentas ou com limite de páginas, eu construí a minha própria.

Precisava converter livros técnicos em PDF para áudio para ouvir no caminho do trabalho — e tudo que encontrei na internet era cheio de limitações: corte de texto, vozes robóticas, sem suporte a português, paywall depois de 10 minutos de áudio. Decidi resolver isso de vez.

## ✨ Funcionalidades

- 📄 Suporte a PDFs digitais e escaneados (OCR automático)
- 🎙️ Vozes neurais naturais via **Edge TTS** (sem API key, sem custo)
- 🌍 Múltiplos idiomas: Português, Inglês, Espanhol, Francês, Alemão
- ⚡ Processamento paralelo de chunks para geração rápida
- 🧹 Limpeza automática de código, URLs e ruídos do texto
- 📦 Download direto do MP3 final
- 🔄 Progresso em tempo real via Server-Sent Events

## 🛠️ Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Uvicorn |
| TTS (Text-to-Speech) | Edge TTS (Microsoft Neural Voices) |
| Extração de PDF | PyPDF2 + pdf2image |
| OCR | Tesseract |
| Áudio | pydub + ffmpeg |
| Frontend | HTML/CSS/JS puro |

## 🚀 Rodando localmente

### Pré-requisitos

```bash
# Linux/Ubuntu
sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr tesseract-ocr-por

# macOS
brew install ffmpeg poppler tesseract tesseract-lang
```

### Instalação

```bash
git clone https://github.com/buckgustavo/Converte-PDF-em-Audiobook.git
cd Converte-PDF-em-Audiobook

pip install -r requirements.txt

uvicorn app:app --reload
```

Acesse: [http://localhost:8000](http://localhost:8000)

## ☁️ Deploy grátis no Render

1. Crie uma conta em [render.com](https://render.com)
2. Conecte este repositório
3. Configure:
   - **Build Command:**
     ```
     apt-get install -y ffmpeg poppler-utils tesseract-ocr tesseract-ocr-por && pip install -r requirements.txt
     ```
   - **Start Command:**
     ```
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```
4. Deploy! 🚀

## 📋 Como usar

1. Acesse a aplicação no navegador
2. Faça upload do seu PDF
3. Escolha idioma, sotaque e velocidade
4. Clique em **Converter**
5. Aguarde o progresso e baixe o MP3

## 💡 Por que construí isso?

Precisava de uma solução para converter livros e artigos técnicos em áudio para aproveitar o tempo no trânsito. Testei diversas ferramentas online e todas tinham algum problema crítico: limite de páginas, vozes péssimas em português, necessidade de cadastro ou simplesmente não funcionavam para PDFs escaneados.

A solução foi construir do zero com FastAPI + Edge TTS — vozes neurais da Microsoft, gratuitas, sem API key, com qualidade surpreendente em português brasileiro.

## 📄 Licença

MIT — use, modifique e distribua à vontade.
