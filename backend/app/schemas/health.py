from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    app: str
    env: str


class ReadinessOut(BaseModel):
    """Only ever the good answer: a dependency that failed is a 503 in the
    shared error envelope, with the same `checks` under `detail`."""

    status: Literal["ready"]
    checks: dict[str, str]
