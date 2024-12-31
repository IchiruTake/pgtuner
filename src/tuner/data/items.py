import string
from pprint import pformat
from typing import Any, Callable
from pydantic import BaseModel, Field
from enum import Enum, auto, verify, CONTINUOUS

__all__ = ["PG_TUNE_ITEM"]


# =============================================================================
# This section is managed by the application
@verify(CONTINUOUS)
class OUTPUT_MODE(int, Enum):
    BASE = auto()
    BASE_WITH_COMMENT = auto()
    FORCE = auto()
    FORCE_WITH_COMMENT = auto()

class PG_TUNE_ITEM(BaseModel):
    key: str = Field(..., description="The key of the sysctl configuration", frozen=True)
    before: Any = Field(..., description="The system information value before tuning", frozen=True)
    after: Any = Field(..., description="The system information value after tuning", frozen=False)
    comment: str | None = Field(None, description="The comment about the tuning process", frozen=True)
    style: str | None = Field(
        default="$1 = '$2'", frozen=True,
        description="The style of the tuning process. This is used to determine the style of the tuning"
    )

    # Custom-reserved variables for developers
    prefix: str | None = Field(None, description="The prefix for the syntax", frozen=True)
    trigger: Any = Field(description="The function that has been used to trigger the tuning for re-try", frozen=True)
    partial_func: Callable | None = (
        Field(default=None, frozen=True,
              description="The partial function to output the result after finish the tuning")
    )

    def out(self, output_if_difference_only: bool = False, include_comment: bool = False) -> str:
        if output_if_difference_only and self.before == self.after:
            return ''
        texts = []
        if include_comment:
            comment = str(pformat(self.comment)).replace('\n', '\n# ')
            texts.append(f"# {comment}")

        style = self.style or "$1 = $2"
        assert "$1" in style and "$2" in style, f"Invalid style configuration: {style} due to missing $1 and $2"
        if self.prefix:
            style = ' '.join((self.prefix, style))
        if '  ' in style:
            style = ' '.join(style.split())
        after: str = self.out_display()
        style = style.replace("$1", self.key).replace("$2", after).strip()
        texts.append(f'\n{style}' if texts else style)
        return ''.join(texts)

    def out_display(self) -> str:
        after = self.after
        if self.partial_func is not None:
            after = self.partial_func(after)
        if isinstance(after, float):
            precision = self.float_precision()
            after = f'{round(after, precision):.{precision}f}'
        if not isinstance(after, str):
            after = str(after)
        # Wrap the text
        if isinstance(self.after, str) and (' ' in after or any(char in string.punctuation for char in after)):
            after = f"'{after}'"
        return after

    @staticmethod
    def float_precision() -> int:
        return 4

    @staticmethod
    def cast(value: float) -> float:
        precision = PG_TUNE_ITEM.float_precision()
        return round(value, precision)

    def transform_keyname(self) -> str:
        # Text Transformation: Remove underscores to whitespace and capitalize the first character of each letter
        return ' '.join([x.capitalize() for x in self.key.split('_')])