from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DOCS_DIR = BASE_DIR / "docs"
NOTIFY_DIR = BASE_DIR / "notify"


def read_markdown(directory: Path, filename: str) -> str:
    path = directory / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} nao encontrado")
    return path.read_text(encoding="utf-8")


def markdown_response(directory: Path, filename: str) -> PlainTextResponse:
    return PlainTextResponse(read_markdown(directory, filename), media_type="text/markdown; charset=utf-8")
