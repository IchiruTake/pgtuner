from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.static.vars import PGTUNER_PROFILE_FILE_PATH
from src.tuner.data.scope import PG_SCOPE
from src.tuner.external.psutil_api import SERVER_SNAPSHOT
from src.tuner.data.connection import PG_CONNECTION
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.items import PG_TUNE_ITEM

__all__ = ["PG_TUNE_REQUEST", "PG_SYS_SHARED_INFO"]

# =============================================================================
class PG_TUNE_REQUEST(BaseModel):
    """ The PostgreSQL tuning request, initiated by the user's request for tuning up """
    connection: PG_CONNECTION
    options: PG_TUNE_USR_OPTIONS
    output_if_difference_only: bool = False
    include_comment: bool = False

# This section is managed by the application
class PG_SYS_SHARED_INFO(BaseModel):
    f"""
    This class is used to store the shared system information that captures the report generated from the application,
    and also be used to store every application-managed tuning input and output.
    
    Parameters:
    ----------
    vm_snapshot: SERVER_SNAPSHOT | None
        The snapshot of the server information (including the vCPU and memory).

    """
    vm_snapshot: SERVER_SNAPSHOT = (
        Field(description="The snapshot of the server information", frozen=False)
    )
    backup: dict[str, dict[str, Any] | None] | None = (
        Field(default_factory=lambda: defaultdict(dict),
              description="The backup of the system information to supply in the tuning item (ignored as "
                          "it is not helpful", frozen=False)
    )

    # Don't change the whole variable here
    outcome: dict[
        Literal['kernel', 'database'],
        dict[
            Literal['sysctl', 'boot', 'config'],
            dict[
                PG_SCOPE,
                dict[str, PG_TUNE_ITEM]
            ]
        ]
    ] = (
        Field(default_factory=lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))), frozen=True,
              description="The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.")
    )
    outcome_cache: dict[
        Literal['kernel', 'database'],
        dict[
            Literal['sysctl', 'boot', 'config'],
            dict[str, Any]
        ]
    ] = (
        Field(default_factory=lambda: defaultdict(lambda: defaultdict(dict)), frozen=True,
              description="The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.")
    )

    def get_managed_items(self, large_scope: Literal['kernel', 'database'],
                          sub_scope: Literal['sysctl', 'boot', 'config'],
                          scope: PG_SCOPE) -> dict[str, PG_TUNE_ITEM]:
        return self.outcome[large_scope][sub_scope][scope]

    def get_managed_cache(self, large_scope: Literal['kernel', 'database'],
                          sub_scope: Literal['sysctl', 'boot', 'config']) -> dict[str, Any]:
        return self.outcome_cache[large_scope][sub_scope]

    def get_managed_item_and_cache(self, large_scope: Literal['kernel', 'database'],
                                   sub_scope: Literal['sysctl', 'boot', 'config'],
                                   scope: PG_SCOPE) -> tuple[dict[str, PG_TUNE_ITEM], dict[str, Any]]:
        return self.get_managed_items(large_scope, sub_scope, scope), self.get_managed_cache(large_scope, sub_scope)

    def sync_cache_from_items(self, large_scope: Literal['kernel', 'database'],
                              sub_scope: Literal['sysctl', 'boot', 'config']) -> dict:
        divergent = {}
        for scope, items in self.outcome[large_scope][sub_scope].items():
            for item_name, item in items.items():
                current = self.outcome_cache[large_scope][sub_scope].get(item_name)
                if current != item.after:
                    divergent[item_name] = item.after
                    self.outcome_cache[large_scope][sub_scope][item_name] = item.after
        return divergent