import decimal
import math
from pydantic import ByteSize

from src.static.vars import DB_PAGE_SIZE

__all__ = ['bytesize_to_hr', 'bytesize_to_postgres_unit', 'realign_value', 'cap_value']
_SIZING = ByteSize | int | float


def bytesize_to_hr(bytesize: int, separator: str = ' ') -> str:
    if isinstance(bytesize, float):
        bytesize = int(bytesize)

    return ByteSize(bytesize).human_readable(separator=separator)


def bytesize_to_postgres_unit(value: _SIZING, unit: _SIZING = DB_PAGE_SIZE, min_unit: _SIZING | None = None) -> int | str:
    assert min_unit > 0, 'The minimum unit must be greater than zero'
    assert unit > 0, 'The unit must be greater than zero'
    if min_unit is None:
        min_unit = unit
    elif min_unit > unit:
        raise ValueError('P1: The minimum unit must be smaller than the unit')
    if unit % min_unit != 0:
        raise ValueError('P1: The unit must be divisible by the minimum unit.')
    if isinstance(value, float):
        value = int(value)

    value = ByteSize(value) if isinstance(value, int) else value
    d_min, m_min = divmod(value, min_unit)
    value: int = min_unit * (d_min + 1 if m_min >= ((min_unit + 1) // 2) else d_min)
    return value // unit   # PostgreSQL does not understand the float value


def realign_value(value: int | ByteSize, page_size: int = DB_PAGE_SIZE) -> tuple[int, int]:
    # This function is used to ensure we re-align the :var:`value` to the nearest page size
    d, m = divmod(int(value), page_size)
    return d * page_size, (d + (1 if m > 0 else 0)) * page_size


def cap_value(value: _SIZING, min_value: _SIZING, max_value: _SIZING,
              redirect_number: tuple[_SIZING, _SIZING] = None) -> _SIZING:
    if redirect_number is not None and len(redirect_number) == 2 and value == redirect_number[0]:
        value = redirect_number[1]
    return min(max(ByteSize(value) if isinstance(value, (ByteSize, int)) else value, min_value), max_value)
