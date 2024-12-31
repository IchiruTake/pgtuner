import os
from typing import Any, Callable

__all__ = ["GetEnvVar", ]

def GetEnvVar(var_names: list[str] | None, default: Any,
              input_message_string: str = None,
              env_type_cast_fn: Callable[[str], Any] = None,
              input_type_cast_fn: Callable[[str], Any] = None) -> Any:
    """
    This function is a helper function to get the environment variable or the user input.
    If the requested variable is not configured, then the user would be asked to input the value (if not specified).
    If the :var:`input_message_string` is not specified, then the :var:`default` value would be returned.
    The priority order is the environment variable (:var:`var_names`), then the user input (through answer
    :var:`input_message_string`), and finally the default value (:var:`default`).

    Parameters:
    ----------

    var_names: list[str]
        The list of environment variable names to be checked.

    default: Any
        The default value if the environment variable is not set and the user does not provide the input.

    input_message_string: str
        The message string to ask the user to input the value. If not specified, then the default value would be
        returned.

    input_type_cast_fn: Callable[[str], Any]
        The function to cast the input string to the desired type. This is only enabled when the user input is
        requested. If not specified, then the input would be treated as a string.

    Returns:
    -------

    Any
        The value of the environment variable or the user input or the default value.

    """
    response: Any = None
    if isinstance(var_names, list):
        for var_name in var_names:
            response = os.getenv(var_name)
            if response is not None:  # This must not be an empty string
                return response if not env_type_cast_fn else env_type_cast_fn(response)

    if response is not None and input_message_string:
        response: str = input(input_message_string).strip()
        if response:  # This must not be an empty string
            return response if not input_type_cast_fn else input_type_cast_fn(response)

    return default
