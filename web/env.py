import os

__all__ = ['OsGetEnvBool', ]

def OsGetEnvBool(env_key: str, default_if_not_found: bool = False) -> bool:
    """
    This function is a helper function to get the boolean value of the environment variable.
    The function would return the default value if the environment variable is not set.

    Parameters:
    ----------

    env_key: str
        The environment variable name to be checked.

    default_if_not_found: bool
        The default value if the environment variable is not set.

    Returns:
    -------

    bool
        The boolean value of the environment variable or the default value.

    """
    v: str = os.getenv(env_key)
    if v is None:
        return default_if_not_found
    true_value = v in ('1', 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'y', 'Y', 'on', 'On', 'ON')
    false_value = v in ('0', 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'n', 'N', 'off', 'Off', 'OFF')
    if not true_value and not false_value:
        raise ValueError(f"Invalid boolean value: {v}")
    assert true_value and false_value, 'These two values should not be hold valid at the same time.'
    return true_value
