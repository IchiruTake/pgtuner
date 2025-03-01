
__all__ = ['generalized_mean']

def generalized_mean(*args: int | float, level: int | float, round_ndigits: int | None = 4) -> int | float:
    """
    This function is used to calculate the average of the given arguments using the power of the level.
    If level = 1, it will be the same as the normal average.
    Ref: https://en.wikipedia.org/wiki/Generalized_mean

    Arguments:
    ---------

    *args: int | float
        The arguments to calculate the average

    level: int | float
        The power of the average. If level = 1, it will be the same as the normal average. For negative values,
        it will be towards to the smallest number in the list. For positive values, it will be towards to the
        largest

    round_ndigits: int | None
        The number of digits to round the result, which uses the built-in round() function in Python
    """

    if level == 0:
        level = 1e-6    # Small value to prevent division by zero
    elif level == -0:
        level = -1e-6
    n = len(args)
    return round((sum((arg ** level) / n for arg in args)) ** (1 / level), ndigits=round_ndigits)
