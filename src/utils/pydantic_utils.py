from pydantic import ByteSize
from src.utils.static import DB_PAGE_SIZE

__all__ = ['bytesize_to_hr', 'realign_value', 'cap_value']
_SIZING = ByteSize | int | float


def bytesize_to_hr(bytesize: int, separator: str = ' ') -> str:
    if isinstance(bytesize, float):
        bytesize = int(bytesize)

    return ByteSize(bytesize).human_readable(separator=separator)


def realign_value(value: int | ByteSize, page_size: int = DB_PAGE_SIZE) -> tuple[int, int]:
    # This function is used to ensure we re-align the :var:`value` to the nearest page size
    d, m = divmod(int(value), page_size)
    return d * page_size, (d + (1 if m > 0 else 0)) * page_size


def cap_value(value: _SIZING, min_value: _SIZING, max_value: _SIZING,
              redirect_number: tuple[_SIZING, _SIZING] = None) -> _SIZING:
    if redirect_number is not None and len(redirect_number) == 2 and value == redirect_number[0]:
        value = redirect_number[1]
    return min(max(ByteSize(value) if isinstance(value, (ByteSize, int)) else value, min_value), max_value)
