import os
import time
import subprocess
import requests

DEFAULT_URL = "http://127.0.0.1:8002"


def ensure_backend_running(url: str | None = None) -> str:
    """Garante que o backend FastAPI está rodando. Se não estiver, inicia e espera /health.
    Retorna a URL final.
    """
    url = (url or os.getenv("CONTEXT_BUILDER_URL") or DEFAULT_URL).strip()
    # já está no ar?
    try:
        r = requests.get(url.rstrip("/") + "/health", timeout=2)
        if r.ok:
            return url
    except Exception:
        pass
    # não respondeu: iniciar subprocesso
    # tenta porta padrão 8002
    proc = subprocess.Popen([
        os.path.join(os.getcwd(), ".venv", "Scripts", "uvicorn.exe"),
        "app.main:app", "--port", "8002"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    # aguarda ficar saudável
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            r = requests.get(url.rstrip("/") + "/health", timeout=2)
            if r.ok:
                return url
        except Exception:
            time.sleep(0.5)
    # se não subiu, mata processo e retorna url mesmo assim para logs
    try:
        proc.terminate()
    except Exception:
        pass
    return url
