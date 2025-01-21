from pydantic import ByteSize
from src.static.vars import DB_PAGE_SIZE

__all__ = ['bytesize_to_hr', 'bytesize_to_postgres_string', 'bytesize_to_postgres_unit',
           'realign_value_to_unit', 'cap_value']
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


def realign_value_to_unit(value: int | ByteSize, page_size: int = DB_PAGE_SIZE) -> tuple[int, int]:
    # This function is used to ensure we re-align the :var:`value` to the nearest page size
    d, m = divmod(int(value), page_size)
    return d * page_size, (d + (1 if m > 0 else 0)) * page_size


def cap_value(cvar: _SIZING, min_value: _SIZING, max_value: _SIZING,
              redirect_number: tuple[_SIZING, _SIZING] = None) -> _SIZING:
    if redirect_number is not None and len(redirect_number) == 2 and cvar == redirect_number[0]:
        cvar = redirect_number[1]
    return min(max(ByteSize(cvar) if isinstance(cvar, (ByteSize, int)) else cvar, min_value), max_value)