from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Route = Literal["billing", "orders"]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    route: Route
    reason: str = Field(min_length=1, max_length=500)


class Ticket(BaseModel):
    """Ground-truth labels belong to evaluation only, never graph state."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=20000)
    expected_route: Route
