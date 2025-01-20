from pydantic import ByteSize
from src.static.vars import DB_PAGE_SIZE

__all__ = ["bytesize_to_hr"]
_SIZING = ByteSize | int | float


def bytesize_to_hr(bytesize: int, separator: str = ' ') -> str:
    return ByteSize(bytesize).human_readable(separator=separator)


def bytesize_to_postgres_string(value: _SIZING) -> str:
    return bytesize_to_hr(value, separator='').strip().replace('i', '').replace('K', 'k')


def bytesize_to_postgres_unit(value: _SIZING, unit: _SIZING = DB_PAGE_SIZE, precision: int = 2) -> int | str:
    # This function is used to convert the value to the nearest unit of the page size to be used in the display function
    d, m = divmod(ByteSize(value), unit)
    if precision == 0:
        return int((d + 1) * unit) if m >= (unit + 1) // 2 else int(d * unit)
    if m == 0 or len(str(d)) > 3:  # If the number is too large, we don't need to round it
        precision = 1
    return f'{ByteSize(value) / unit:.{precision}f}'