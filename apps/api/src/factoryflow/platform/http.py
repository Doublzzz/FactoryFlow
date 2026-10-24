"""Transport-only security and safe errors; business modules are injected by bootstrap."""

import hmac
from typing import Annotated

from fastapi import Header, Request, Security
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict

from factoryflow.kernel.contracts import BusinessError


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    code: str
    message: str
    field: str | None = None
    request_id: str


ERROR_RESPONSES = {status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 503)}
session_cookie = APIKeyCookie(name="ff_session", auto_error=False)


def services(request: Request):
    result = request.app.state.services
    if result is None:
        raise BusinessError("NOT_CONFIGURED", 503)
    result.check_ready()
    return result


def require_actor(
    request: Request,
    session_token: Annotated[str | None, Security(session_cookie)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    actor, csrf = services(request).identity.authenticate(session_token)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = csrf_token or ""
        if not supplied or not hmac.compare_digest(supplied.encode(), csrf.encode()):
            raise BusinessError("CSRF_REQUIRED", 403)
    return actor
