from enum import Enum

__all__ = ['PG_SIZING']

_ascending_specs: dict[str, list] = {
    'size': ['mini', 'medium', 'large', 'mall', 'bigt'],
    'vcpu_min': [1, 2, 6, 12, 32],
    'vcpu_max': [4, 8, 16, 48, 128],
    'ram_gib_min': [2, 8, 24, 48, 128],
    'ram_gib_max': [16, 32, 64, 192, 512],
    'storage_gib_max': [50, 300, 1024, 5120, 32768],
    'network_mbps_max': [500, 1000, 5000, 12500, 30000],
}


# =============================================================================
# ENUM choices
class PG_SIZING(str, Enum):
    """
    The PostgreSQL sizing profile. This could help you analyze if your provided server is suitable with our
    defined profiles.
    """
    MINI = 'mini'
    MEDIUM = 'medium'
    LARGE = 'large'
    MALL = 'mall'
    BIGT = 'bigt'

    def _num(self) -> int:
        return _ascending_specs['size'].index(self.value)

    def __lt__(self, other: 'PG_SIZING') -> bool:
        return self._num() < other._num()

    def __le__(self, other: 'PG_SIZING') -> bool:
        return self._num() <= other._num()

    def __gt__(self, other: 'PG_SIZING') -> bool:
        return self._num() > other._num()

    def __ge__(self, other: 'PG_SIZING') -> bool:
        return self._num() >= other._num()

    def __eq__(self, other: 'PG_SIZING') -> bool:
        return self._num() == other._num()

    def __ne__(self, other: 'PG_SIZING') -> bool:
        return self._num() != other._num()

    def __add__(self, other: 'PG_SIZING') -> 'PG_SIZING':
        return PG_SIZING(_ascending_specs['size'][self._num() + other._num()])

    def __sub__(self, other: 'PG_SIZING') -> 'PG_SIZING':
        return PG_SIZING(_ascending_specs['size'][self._num() - other._num()])
