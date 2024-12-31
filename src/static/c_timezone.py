"""
This module contains the datetime and TIMEZONE for the project.
For the usage of timezone, we use the zoneinfo and tzdata packages instead of pytz, which is introduced
since Python 3.9. According to the documentation (https://docs.python.org/3/library/zoneinfo.html#module-zoneinfo),
pytz is not recommended for new projects later than Python 3.9 except backward compatibility. By default, zoneinfo uses
the system’s time zone data if available; if no system time zone data is available, the library will fall back to using
the first-party tzdata package available on PyPI.

"""

from zoneinfo import ZoneInfo
from functools import lru_cache

# ==================================================================================================
__ZONE: str = "Europe/Paris"  # 'UTC' or 'Europe/Paris' or 'Asia/Saigon'
__TIMEZONE: ZoneInfo = ZoneInfo(__ZONE)  # ZoneInfo('UTC') or ZoneInfo('Europe/Paris')


def SwitchTimezone(zone: str) -> None:
    global __ZONE, __TIMEZONE
    try:
        timezone = ZoneInfo(zone)
    except Exception as e:
        
        print(f"{e} Invalid timezone: {zone}")
        return None
    __ZONE = zone
    __TIMEZONE = timezone
    return None


def GetTimezone() -> tuple[ZoneInfo, str]:
    return __TIMEZONE, __ZONE


@lru_cache(maxsize=1)
def PreloadGetUTC() -> tuple[ZoneInfo, str]:
    return ZoneInfo("UTC"), "UTC"
