from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Route = Literal["billing", "orders"]


class RouteDecision(BaseModel):
    """The supervisor's validated route decision; no arbitrary node names."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    route: Route
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False,
                              description="Model-reported routing confidence from 0 to 1; not calibrated accuracy.")


# Backward-compatible name for the first milestone's API and reports.
Decision = RouteDecision


class SupportCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    id: str = Field(min_length=1)
    merchant_name: str = Field(min_length=1)
    shop_domain: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")
    message: str = Field(min_length=1, max_length=20000)
    expected_route: Route


class Ticket(BaseModel):
    """Ground-truth labels belong to evaluation only, never graph state."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=20000)
    expected_route: Route
