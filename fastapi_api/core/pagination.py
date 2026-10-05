from math import ceil
from typing import Tuple, Sequence, Any
from django.db.models import QuerySet
from fastapi_api.core.standard_response import PaginationMeta


def paginate_queryset(queryset: Sequence[Any], page: int, page_size: int) -> Tuple[Sequence[Any], PaginationMeta]:
    """
    Works with both Django QuerySets and plain lists.
    Returns a slice of results and a PaginationMeta object.
    """
    # Count items safely
    if isinstance(queryset, QuerySet):
        total_items = queryset.count()
    else:
        total_items = len(queryset)

    # Compute pagination window
    total_pages = ceil(total_items / page_size) if page_size else 1
    start = (page - 1) * page_size
    end = start + page_size

    # Slice results
    paginated_qs = queryset[start:end]

    meta = PaginationMeta(
        total_items=total_items,
        total_pages=total_pages,
        page=page,
        page_size=page_size,
    )
    return paginated_qs, meta
