from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar('T')

class Page(BaseModel, Generic[T]):
    """Generic pagination response schema."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
