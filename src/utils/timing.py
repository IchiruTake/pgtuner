from time import perf_counter
from typing import Callable
from src.static.vars import K10

__all__ = ['time_decorator']

def time_decorator(func: Callable):
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        if __debug__:
            _time_msg: str = f"Time elapsed for {func.__name__}: {(perf_counter() - start_time) * K10:.2f} ms."
            print(_time_msg)
        return result
    return wrapper
