"""
Backend removido: este projeto usa apenas Streamlit lendo SHEETS_IDS.
"""
raise ImportError("Backend removido. Use Streamlit com SHEETS_IDS.")
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
import hashlib
from pydantic import BaseModel
from pathlib import Path
from .settings import get_settings
from .sheets_loader import collect_sheet_ids, load_raw_rows
from .serializer import build_raw_block


app = FastAPI(title="Context Builder", version="1.0.0")
DATA_DIR = Path("data")
RAW_PATH = DATA_DIR / "context_raw.txt"


class Ask(BaseModel):
    question: str


@app.post("/refresh-cache")
def refresh_cache():
    settings = get_settings()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sheet_ids = collect_sheet_ids(settings.SHEETS_FOLDER_ID, settings.SHEETS_IDS)
    if not sheet_ids:
        # não há planilhas na pasta e nem extras
        # não altera cache se não houver dados
        return {"success": False, "reason": "NO_SHEETS", "rows": 0, "file": str(RAW_PATH), "sheets_found": 0, "by_month": {}}

    df = load_raw_rows(sheet_ids, settings.SHEET_RANGE, settings.YEAR, settings.MONTHS)
    block = build_raw_block(df, settings.SAMPLE_ROWS_PER_MONTH)
    # calcula hash do novo bloco
    new_hash = hashlib.sha256(block.encode("utf-8")).hexdigest()
    old_hash = None
    if RAW_PATH.exists():
        try:
            old_hash = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()
        except Exception:
            old_hash = None
    # conta linhas de dados (não cabeçalhos)
    rows = sum(1 for line in block.splitlines() if line and not line.startswith("Contexto") and not line.startswith("mes="))
    # contagem por mês
    by_month = {}
    if not df.empty:
        for (ano, mes), grp in df.groupby(["ano", "mes"], sort=True):
            by_month[f"{ano}-{mes:02d}"] = int(len(grp))
    # se não mudou e já existia, não sobrescreve
    if old_hash and new_hash == old_hash:
        return {"success": True, "unchanged": True, "rows": rows, "file": str(RAW_PATH), "sheets_found": len(sheet_ids), "by_month": by_month}
    # grava apenas se houver conteúdo
    if rows > 0:
        RAW_PATH.write_text(block, encoding="utf-8")
        return {"success": True, "unchanged": False, "rows": rows, "file": str(RAW_PATH), "sheets_found": len(sheet_ids), "by_month": by_month}
    else:
        # não sobrescreve com vazio
        return {"success": False, "reason": "EMPTY_DATA", "rows": 0, "file": str(RAW_PATH), "sheets_found": len(sheet_ids), "by_month": by_month}


@app.get("/context/raw", response_class=PlainTextResponse)
def get_raw():
    if not RAW_PATH.exists() or RAW_PATH.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="CACHE_EMPTY")
    return RAW_PATH.read_text(encoding="utf-8")


@app.post("/ask")
def ask(p: Ask):
    if not RAW_PATH.exists() or RAW_PATH.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="CACHE_EMPTY")
    raw = RAW_PATH.read_text(encoding="utf-8")
    system = "Use EXCLUSIVAMENTE o bloco 'Contexto (dados das planilhas)'"
    user = raw + "\n\nPergunta: " + p.question
    prompt_preview = f"system: {system}\nuser:\n{user}"
    return {"prompt_preview": prompt_preview}


@app.get("/")
def root():
    return {
        "service": "Context Builder",
        "version": "1.0.0",
        "endpoints": ["/refresh-cache [POST]", "/context/raw [GET]", "/ask [POST]", "/health [GET]", "/status [GET]"]
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    exists = RAW_PATH.exists()
    size = RAW_PATH.stat().st_size if exists else 0
    last_modified = RAW_PATH.stat().st_mtime if exists else None
    return {"cache_exists": exists, "size_bytes": size, "last_modified_ts": last_modified, "path": str(RAW_PATH)}
