"""Pydantic request/response schemas — shared conventions.

One convention rules them all (API.md §1): money crosses the wire as a STRING
with exactly 2 decimals ("105538.46"), never a JSON number — JavaScript never
touches a float. Declare every money field as `Money` and it serializes itself.
"""

from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, PlainSerializer

T = TypeVar("T")


def _as_money(value: Decimal) -> str:
    return f"{value:.2f}"


Money = Annotated[Decimal, PlainSerializer(_as_money, return_type=str)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
