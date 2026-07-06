import contextvars
from uuid import uuid4

_request_id_ctx_var = contextvars.ContextVar("request_id", default=None)

def get_request_id() -> str:
    return _request_id_ctx_var.get()

def set_request_id(request_id: str) -> None:
    _request_id_ctx_var.set(request_id)
