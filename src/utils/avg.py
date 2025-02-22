
__all__ = ['pow_avg']

def pow_avg(*args: int | float, level: int, round_ndigits: int | None = 4) -> int | float:
    # This function is currently used to estimate the average using between normal and hash-based operations
    if level == 0:
        level = 1e-4    # Small value to prevent division by zero
    n = len(args)
    return round((sum((arg ** level) / n for arg in args)) ** (1 / level), ndigits=round_ndigits)
