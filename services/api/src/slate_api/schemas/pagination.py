"""Generic pagination response schema."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope.

    Used by list endpoints to return items alongside total count and
    the page/size parameters that were used to produce the result.
    """

    items: list[T]
    total: int
    page: int
    size: int
