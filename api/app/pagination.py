"""List endpoints accept page / page_size with a documented cap (API.md §1)."""

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def clamp(page: int | None, page_size: int | None) -> tuple[int, int]:
    page = max(1, page or 1)
    size = max(1, page_size or DEFAULT_PAGE_SIZE)
    return page, min(size, MAX_PAGE_SIZE)


def offset(page: int, page_size: int) -> int:
    return (page - 1) * page_size
