"""Interacción con la persona: confirmación y PIN."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SignPrompt:
    document_names: list[str]
    certificate_subject: str
    last_try_warning: bool = False


class UserInterface(Protocol):
    def ask_pin(self, prompt: SignPrompt) -> str | None:
        """Muestra la confirmación y pide el PIN. `None` si cancela o se agota el tiempo."""
