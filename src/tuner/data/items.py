import string
from pprint import pformat
from typing import Any, Callable
from src.tuner.data.sizing import PG_SIZING
from pydantic import BaseModel, Field

__all__ = ['PG_TUNE_ITEM']

# =============================================================================
# This section is managed by the application
_FLOAT_PRECISION = 4

class PG_TUNE_ITEM(BaseModel):
    key: str = Field(..., description="The key of the sysctl configuration", frozen=True)
    before: Any = Field(..., description="The system information value before tuning", frozen=True)
    after: Any = Field(..., description="The system information value after tuning", frozen=False)
    comment: str | None = Field(None, description="The comment about the tuning process", frozen=True)

    # Custom-reserved variables for developers
    style: str | None = Field(
        default="$1 = '$2'", frozen=True,
        description="The style of the tuning process. This is used to determine the style of the tuning"
    )
    trigger: Any = Field(description="The function that has been used to trigger the tuning for re-try", frozen=True)
    partial_func: Callable | None = (
        Field(default=None, frozen=True,
              description="The partial function to output the result after finish the tuning. This override the "
                          "output format on the `after` field.")
    )
    hardware_scope: tuple[str, PG_SIZING] = (
        Field(frozen=True,
              description="The hardware scope of the tuning. The first value is the hardware type, the second value is "
                          "its associated level (mini, medium, large, mall, bigt, ...)")
    )

    def out(self, include_comment: bool = False, custom_style: str | None = None) -> str:
        texts = []
        if include_comment:
            comment = str(pformat(self.comment)).replace('\n', '\n# ')
            texts.append(f"# {comment}")

        style = custom_style or self.style or "$1 = $2"
        assert "$1" in style and "$2" in style, f"Invalid style configuration: {style} due to missing $1 and $2"
        if '  ' in style:
            style = ' '.join(style.split())
        after: str = self.out_display()
        style = style.replace("$1", self.key).replace("$2", after).strip()
        texts.append(f'\n{style}' if texts else style)
        return ''.join(texts)

    def out_display(self, override_value=None) -> str:
        after = self.after
        if override_value is not None:
            after = override_value

        if self.partial_func is not None:  # This function is used when we have hard-coded the output format already
            after = self.partial_func(after)
        elif isinstance(after, float):
            after = f'{round(after, _FLOAT_PRECISION):.{_FLOAT_PRECISION}f}'
        if not isinstance(after, str):  # Force to be the string for easy text wrap-up
            after = str(after)
        if '.' in after:
            # Remove un-necessary whitespace and trailing zeros to beautify the output if it is a float
            after = after.strip().rstrip('0')
            if after.endswith('.'):  # We have over-stripped the trailing zero, add one 'zero' back
                after = f'{after}0'

        # Wrap the text
        if isinstance(self.after, str) and (' ' in after or any(char in string.punctuation for char in after)):
            after = f"'{after}'"
        return after

    def transform_keyname(self) -> str:
        # Text Transformation: Remove underscores to whitespace and capitalize the first character of each letter
        return ' '.join([x.capitalize() for x in self.key.split('_')])

    def __repr__(self):
        return (f"PG_TUNE_ITEM(key={self.key}, before={self.before}, style={self.style}, trigger={self.trigger}, "
                f"after={self.after}, partial_func={self.partial_func}, hardware_scope={self.hardware_scope})")