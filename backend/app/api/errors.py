from typing import Any

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    """Consistent error body: {"detail": {"code": ..., "message": ..., ...}}"""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})
