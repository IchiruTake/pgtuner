from time import perf_counter
from typing import Callable

from src.static.vars import K10

__all__ = ['time_decorator']


def time_decorator(func: Callable):
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        print(f"Time elapsed for {func.__name__}: {(perf_counter() - start_time) * K10:.2f} ms.")
        return result

    return wrapper
