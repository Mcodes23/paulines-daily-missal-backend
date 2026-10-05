from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")

class PaginationMeta(BaseModel):
    total_items: int
    total_pages: int
    page: int
    page_size: int

class StandardResponse(GenericModel, Generic[T]):
    success: bool = True
    message: str = "Success"
    data: Optional[T] = None
    meta: Optional[PaginationMeta] = None

    @classmethod
    def ok(cls, data: Optional[T] = None, message: str = "Success", meta: Optional[PaginationMeta] = None):
        """Wrap success response."""
        return cls(success=True, message=message, data=data, meta=meta)

    @classmethod
    def error(cls, message: str = "An error occurred", meta: Optional[dict] = None):
        """Wrap error response."""
        return cls(success=False, message=message, data=None, meta=meta)
