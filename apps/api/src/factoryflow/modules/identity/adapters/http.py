from typing import Annotated, Literal

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import (
    ERROR_RESPONSES,
    StrictDTO,
    require_actor,
    services,
    session_cookie,
)
from fastapi import APIRouter, Depends, Request, Response, Security
from pydantic import Field

router = APIRouter(prefix="/auth", tags=["Local identity"], responses=ERROR_RESPONSES)


class LoginInput(StrictDTO):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128, repr=False)


class SessionUser(StrictDTO):
    id: str
    username: str
    role: Literal["admin", "operator", "viewer"]


class SessionResponse(StrictDTO):
    user: SessionUser
    csrf_token: str


def user_view(actor: Actor):
    return {"id": str(actor.user_id), "username": actor.username, "role": actor.role}


@router.post("/login", operation_id="login", response_model=SessionResponse)
def login(body: LoginInput, request: Request, response: Response):
    runtime = services(request)
    result = runtime.identity.login(body.username, body.password)
    response.set_cookie(
        "ff_session",
        result["session_token"],
        httponly=True,
        secure=runtime.settings.secure_cookies,
        samesite="strict",
        max_age=43200,
        path="/api/v1",
    )
    return {"user": user_view(result["actor"]), "csrf_token": result["csrf_token"]}


@router.get("/session", operation_id="getSession", response_model=SessionResponse)
def session(request: Request, token: Annotated[str | None, Security(session_cookie)]):
    actor, csrf = services(request).identity.authenticate(token)
    return {"user": user_view(actor), "csrf_token": csrf}


@router.post("/logout", operation_id="logout", status_code=204)
def logout(request: Request, response: Response, actor: Annotated[Actor, Depends(require_actor)]):
    services(request).identity.logout(request.cookies["ff_session"], actor)
    response.delete_cookie("ff_session", path="/api/v1")
