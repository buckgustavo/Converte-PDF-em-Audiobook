# 📖➡️🎧 PDF para Audiobook

Cansado de ferramentas online ruins, lentas ou com limite de páginas, eu construí a minha própria.

Precisava converter livros técnicos em PDF para áudio para ouvir no caminho do trabalho — e tudo que encontrei na internet era cheio de limitações: corte de texto, vozes robóticas, sem suporte a português, paywall depois de 10 minutos de áudio. Decidi resolver isso de vez.

## ✨ Funcionalidades

- 📄 PDFs digitais e escaneados (OCR automático **por página** — funciona em PDFs mistos)
- 🎙️ Vozes neurais naturais via **Edge TTS** (sem API key, sem custo), com **prévia da voz** antes de converter
- 🌍 Português (BR/PT), Inglês (US/UK/AU), Espanhol (ES/MX), Francês, Alemão e Italiano — vozes masculinas e femininas
- 📚 **Capítulos** a partir do sumário do PDF (ou dos títulos detectados), em **MP3** (ID3 CHAP) ou **M4B**
- 💻 **Modo livro técnico** (ver abaixo)
- 🧹 Remove cabeçalhos, rodapés e números de página repetidos; corrige hifenização
- 🎚️ Velocidade ajustável, intervalo de páginas, cancelamento e fila de conversões
- 🔄 Progresso em tempo real (SSE) com estimativa de tempo restante

## 💻 Modo livro técnico

Pensado para livros como *O Programador Pragmático*, *Código Limpo* e afins:

| No PDF | Na narração |
|---|---|
| Títulos e capítulos | Pausa antes/depois, lidos por uma **segunda voz** |
| `Dica 14: ...` / `Tip 14 ...` / `Nota:` / `Aviso:` | Destacados com a segunda voz e pausas |
| Bloco de código (fonte monoespaçada) | *"Exemplo de código em Python, com 12 linhas."* — ou pular, ou ler linha a linha |
| `getUserName()`, `max_retries`, `os.path` | "get User Name", "max retries", "os ponto path" |
| C++, C#, JSON, DRY, YAGNI, SQL, I/O… | Pronúncia natural ("C mais mais", "jêisson", "drai"…) |

O código é detectado pela **fonte monoespaçada** do PDF, não por regex — então frases como *"for each item, import the data"* não são mais apagadas por engano. A linguagem (Python, Ruby, Elixir, Java, JS, Go, Rust, SQL, terminal…) é identificada automaticamente.

O dicionário de pronúncias fica em [`audiobook/text.py`](audiobook/text.py) (`PRONUNCIAS`) — é só adicionar termos.

## 🛠️ Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Uvicorn |
| TTS | Edge TTS (Microsoft Neural Voices) |
| Extração de PDF | PyMuPDF (texto, fontes, sumário) |
| OCR | Tesseract |
| Áudio / capítulos | ffmpeg + mutagen |
| Frontend | HTML/CSS/JS puro |

## 🚀 Rodando localmente

```bash
# Dependências do sistema
sudo apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-por   # Linux
brew install ffmpeg tesseract tesseract-lang                      # macOS

git clone https://github.com/buckgustavo/Converte-PDF-em-Audiobook.git
cd Converte-PDF-em-Audiobook
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app:app --reload
```

Acesse: [http://localhost:8000](http://localhost:8000)

Ou com Docker: `docker compose up -d --build`

### Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## ☁️ Deploy no Amazon Lightsail

Funciona em uma instância Ubuntu de 1 GB (com `MAX_CONCURRENT_JOBS=1`); 2 GB é mais confortável para livros escaneados.

**1. Instale Docker e nginx na instância** (via SSH):

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx git
sudo usermod -aG docker $USER && newgrp docker
```

**2. Suba a aplicação:**

```bash
git clone https://github.com/buckgustavo/Converte-PDF-em-Audiobook.git
cd Converte-PDF-em-Audiobook
docker compose up -d --build
curl localhost:8000/healthz   # {"ok":true,...}
```

**3. Configure o nginx** (o SSE de progresso precisa de `proxy_buffering off`, já incluso):

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/audiobook
sudo nano /etc/nginx/sites-available/audiobook        # ajuste server_name
sudo ln -s /etc/nginx/sites-available/audiobook /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

**4. No console do Lightsail**, em *Networking*: anexe um **IP estático** e libere as portas **80** e **443** no firewall.

**5. HTTPS (opcional, com domínio):**

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com
```

**Atualizar** depois de um `git push`:

```bash
cd Converte-PDF-em-Audiobook && git pull && docker compose up -d --build
```

### Configuração (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | `2` (`1` no compose) | Conversões simultâneas; as demais ficam na fila |
| `MAX_UPLOAD_MB` | `200` | Tamanho máximo do PDF |
| `JOB_TTL_HOURS` | `6` | Por quanto tempo o áudio pronto fica disponível para download |
| `TTS_CONCURRENCY` | `6` | Requisições paralelas ao Edge TTS por conversão |
| `DATA_DIR` | `/tmp/pdf2audiobook` | Onde ficam PDFs e áudios temporários |

> ⚠️ Rode com **um único worker** do Uvicorn: a fila de jobs fica em memória.

## 📡 API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/voices` | Idiomas e vozes disponíveis |
| `POST` | `/api/preview` | Prévia da voz (`voz`, `velocidade`, `texto`) → MP3 |
| `POST` | `/api/convert` | Envia o PDF (`file`, `voz`, `velocidade`, `modo_tecnico`, `codigo`, `voz_destaque`, `pagina_inicio`, `pagina_fim`, `formato`, `chunk_size`) → `job_id` |
| `GET` | `/api/jobs/{id}` | Estado do job |
| `GET` | `/api/progress/{id}` | Progresso via SSE (reconexão segura) |
| `DELETE` | `/api/jobs/{id}` | Cancela |
| `GET` | `/api/download/{id}` | Baixa o MP3/M4B |

## 💡 Por que construí isso?

Precisava de uma solução para converter livros e artigos técnicos em áudio para aproveitar o tempo no trânsito. Testei diversas ferramentas online e todas tinham algum problema crítico: limite de páginas, vozes péssimas em português, necessidade de cadastro ou simplesmente não funcionavam para PDFs escaneados.

A solução foi construir do zero com FastAPI + Edge TTS — vozes neurais da Microsoft, gratuitas, sem API key, com qualidade surpreendente em português brasileiro.

## 📄 Licença

MIT — use, modifique e distribua à vontade.
