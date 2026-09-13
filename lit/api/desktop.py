"""Desktop helpers: open Edge split view, etc."""

from __future__ import annotations

import logging
import platform

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lit.services.split_browser import find_msedge, launchable_http_url, open_edge_split

logger = logging.getLogger("lit.desktop")
router = APIRouter(prefix="/api/desktop", tags=["desktop"])


class SplitOpenBody(BaseModel):
    left: str
    right: str


@router.post("/open-split")
def open_split(body: SplitOpenBody) -> dict[str, str | bool]:
    left = launchable_http_url(body.left)
    right = launchable_http_url(body.right)
    if not left or not right:
        raise HTTPException(
            status_code=400,
            detail="Both left and right must be http(s) URLs",
        )
    if platform.system() != "Windows":
        raise HTTPException(
            status_code=501,
            detail="Split view opens Microsoft Edge on Windows",
        )
    if not find_msedge():
        raise HTTPException(status_code=500, detail="Microsoft Edge was not found")
    try:
        result = open_edge_split(left, right)
    except Exception as exc:
        logger.exception("Edge split view failed")
        raise HTTPException(status_code=500, detail="Could not open Edge split view") from exc
    return {"status": "ok", "positioned": bool(result.get("positioned"))}
