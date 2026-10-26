"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..application import Application


def get_application(request: Request) -> Application:
    return request.app.state.application


AppDep = Annotated[Application, Depends(get_application)]
