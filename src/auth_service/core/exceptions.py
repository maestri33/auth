from __future__ import annotations

from fastapi import HTTPException, status


class NotFound(HTTPException):
    def __init__(self, detail: str = "nao encontrado") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class Conflict(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BadRequest(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class Unauthorized(HTTPException):
    def __init__(self, detail: str = "nao autenticado") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
