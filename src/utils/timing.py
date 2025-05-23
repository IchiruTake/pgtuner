from time import perf_counter
from typing import Callable

from src.utils.static import K10

__all__ = ['time_decorator']


def time_decorator(func: Callable):
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        print(f"Time elapsed for {func.__name__}: {(perf_counter() - start_time) * K10:.3f} ms.")
        return result

    return wrapper
