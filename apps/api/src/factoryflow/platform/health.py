from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/health", tags=["Operations"])


class Liveness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    service: Literal["FactoryFlow"] = "FactoryFlow"
    version: str = "0.1.0"


@router.get("/live", response_model=Liveness, operation_id="getLiveness")
def get_liveness() -> Liveness:
    """Process liveness only; this does not verify business storage readiness."""
    return Liveness()
