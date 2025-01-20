import logging
from typing import Callable, Any

from src.static.vars import APP_NAME_UPPER

_logger = logging.getLogger(APP_NAME_UPPER)


def FactoryForPydanticWithUserFn(message: str, user_fn: Callable[[Any], Any] | None,
                                 default_value: Any) -> Callable[[], Any]:
    try:
        if user_fn is not None:
            return lambda: (user_fn(input(message).strip()) or default_value)
        return lambda: (input(message).strip() or default_value)
    except Exception as e:
        _logger.error(f"Error: {e}")

    return lambda: default_value
