import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    import importlib
    import app as app_module
    app_module = importlib.reload(app_module)

    def falso_gerar(pdf, saida, op, progress_cb, cancelado):
        progress_cb(50, "Gerando áudio 1/2...")
        with open(saida, "wb") as f:
            f.write(b"ID3fake")
        from audiobook import Resultado
        return Resultado(10, 3.5, [{"titulo": "Início", "inicio": 0.0}], [])

    monkeypatch.setattr(app_module, "gerar_audiobook", falso_gerar)
    with TestClient(app_module.app) as c:
        yield c


def _esperar(client, job_id):
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job não terminou")


def test_vozes(client):
    data = client.get("/api/voices").json()
    assert "pt" in data["idiomas"]
    assert any(v["id"] == "pt-BR-FranciscaNeural" for v in data["vozes"])


def test_fluxo_completo(client, pdf_tecnico):
    with open(pdf_tecnico, "rb") as f:
        r = client.post("/api/convert", files={"file": ("Meu Livro.PDF", f, "application/pdf")},
                        data={"formato": "m4b"})
    assert r.status_code == 200
    job = _esperar(client, r.json()["job_id"])
    assert job["status"] == "done"
    assert job["resultado"]["palavras"] == 10

    # SSE entrega o estado final mesmo conectando depois do fim (reconexão segura)
    with client.stream("GET", f"/api/progress/{job['id']}") as s:
        corpo = "".join(s.iter_text())
    assert '"status": "done"' in corpo

    d = client.get(f"/api/download/{job['id']}")
    assert d.status_code == 200
    assert d.headers["content-type"] == "audio/mp4"
    assert "Meu%20Livro.m4b" in d.headers["content-disposition"]


def test_rejeita_arquivo_que_nao_e_pdf(client):
    r = client.post("/api/convert", files={"file": ("x.pdf", b"nao sou pdf", "application/pdf")})
    assert r.status_code == 400


def test_limite_de_upload(client, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "MAX_UPLOAD_MB", 0)
    r = client.post("/api/convert", files={"file": ("x.pdf", b"%PDF-1.4 conteudo", "application/pdf")})
    assert r.status_code == 413


def test_job_inexistente(client):
    assert client.get("/api/jobs/nao-existe").status_code == 404
    assert client.get("/api/download/nao-existe").status_code == 404


def test_cancelamento(client, pdf_tecnico, monkeypatch):
    import app as app_module

    def lento(pdf, saida, op, progress_cb, cancelado):
        for _ in range(100):
            if cancelado():
                raise InterruptedError
            time.sleep(0.02)
        raise AssertionError("não foi cancelado")

    monkeypatch.setattr(app_module, "gerar_audiobook", lento)
    with open(pdf_tecnico, "rb") as f:
        job_id = client.post("/api/convert", files={"file": ("a.pdf", f, "application/pdf")}).json()["job_id"]
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert _esperar(client, job_id)["status"] == "canceled"
