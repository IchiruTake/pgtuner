from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.items import PG_TUNE_ITEM
import logging
from src.static.vars import APP_NAME_UPPER

__all__ = ['PG_TUNE_REQUEST', 'PG_TUNE_RESPONSE']
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
class PG_TUNE_REQUEST(BaseModel):
    """ The PostgreSQL tuning request, initiated by the user's request for tuning up """
    options: PG_TUNE_USR_OPTIONS
    output_if_difference_only: bool = False
    include_comment: bool = False
    custom_style: str | None = None


# This section is managed by the application
class PG_TUNE_RESPONSE(BaseModel):
    """
    This class is to store the tuning result of the PostgreSQL system per each request
    """
    # Don't change the whole variable here
    outcome: dict[
        PGTUNER_SCOPE,
        dict[
            PG_SCOPE,
            dict[str, PG_TUNE_ITEM]
        ]
    ] = (
        Field(default_factory=lambda: defaultdict(lambda: defaultdict(dict)), frozen=True,
              description="The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.")
    )
    outcome_cache: dict[
        PGTUNER_SCOPE,
        dict[str, Any]
    ] = (
        Field(default_factory=lambda: defaultdict(dict), frozen=True,
              description="The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.")
    )

    def get_managed_items(self, target: PGTUNER_SCOPE, scope: PG_SCOPE) -> dict[str, PG_TUNE_ITEM]:
        return self.outcome[target][scope]

    def get_managed_cache(self, target: PGTUNER_SCOPE) -> dict[str, Any]:
        return self.outcome_cache[target]

    def get_managed_item_and_cache(self, target: PGTUNER_SCOPE, scope: PG_SCOPE) -> tuple[dict[str, PG_TUNE_ITEM], dict[str, Any]]:
        return self.get_managed_items(target, scope), self.get_managed_cache(target)

    def sync_cache_from_items(self, target: PGTUNER_SCOPE) -> dict:
        divergent = {}
        managed_cache = self.get_managed_cache(target)
        for scope, items in self.outcome[target].items():
            for item_name, item in items.items():
                current = managed_cache.get(item_name)
                if current != item.after:
                    divergent[item_name] = item.after
                    managed_cache = item.after
        return divergent

    def _generate_content_as_file(self, target: PGTUNER_SCOPE, request: PG_TUNE_REQUEST, backup_settings: bool = True,
                                  exclude_names: list[str] | set[str] = None) -> str:
        content: list[str] = [target.disclaimer(), '\n']
        if backup_settings:
            content.append(f'# User Options: {request.options.model_dump(exclude={'vm_snapshot'})}\n')
        for idx, (scope, items) in enumerate(self.outcome[target].items()):
            content.append(f'## ============================== SCOPE: {scope} ============================== \n')
            for item_name, item in items.items():
                if exclude_names is None or item_name not in exclude_names:
                    content.append(item.out(request.output_if_difference_only, request.include_comment,
                                            request.custom_style))
                    content.append('\n' * (2 if request.include_comment else 1))
            # Separate for better view
            if request.include_comment:
                content.append('\n\n\n')
            else:
                content.append('\n')
        return ''.join(content)

    def _generate_content_as_response(self, target: PGTUNER_SCOPE, exclude_names: list[str] | set[str] = None,
                                      output_format = 'conf') -> str | dict[str, Any]:
        content = {
            item_name: item.out_display(override_value=None)
            for _, items in self.outcome[target].items() for item_name, item in items.items()
            if exclude_names is None or item_name not in exclude_names
        }
        if output_format == 'text':
            content = ';\n'.join(f'{k} = {v}' for k, v in content.items())
        elif output_format == 'conf':
            content = '\n'.join(f'{k} = {v}' for k, v in content.items())
        return content

    def generate_content(self, target: PGTUNER_SCOPE, request: PG_TUNE_REQUEST,
                         exclude_names: list[str] | set[str] = None, backup_settings: bool = True,
                         output_format: Literal['json', 'text', 'conf', 'file'] = 'conf') -> str:
        if exclude_names is not None and isinstance(exclude_names, list):
            exclude_names = set(exclude_names)
        if output_format == 'file':
            return self._generate_content_as_file(target, request, backup_settings, exclude_names)
        elif output_format in ('json', 'text', 'conf'):
            return self._generate_content_as_response(target, exclude_names, output_format)

        msg: str = f'Invalid output format: {output_format}. Expected one of "json", "text", "conf", "file".'
        _logger.error(msg)
        raise ValueError(msg)