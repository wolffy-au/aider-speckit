from typing import List, Literal, Tuple, Union

from ..dump import dump  # noqa: F401
from .base_coder import Coder
from .help_prompts import HelpPrompts


class HelpCoder(Coder):
    """Interactive help and documentation about aider."""

    edit_format = "help"
    gpt_prompts = HelpPrompts()

    def get_edits(
        self, mode: Literal["update", "diff"] = "update"
    ) -> Union[List[Tuple[str, str, Union[str, List[str]]]], str]:
        return super().get_edits(mode)

    def apply_edits(self, edits, dry_run: bool = False):
        pass
