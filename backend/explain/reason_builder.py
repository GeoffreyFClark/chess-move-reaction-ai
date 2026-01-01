"""ReasonBuilder class for accumulating move explanation reasons."""


class ReasonBuilder:
    """Accumulates reasons for a move evaluation without duplicates."""

    def __init__(self) -> None:
        self._reasons: list[str] = []

    def add(self, text: str) -> None:
        """Add a reason if it's not empty and not already present.

        Args:
            text: The reason text to add.
        """
        if text and text not in self._reasons:
            self._reasons.append(text)

    def extend(self, texts: list[str]) -> None:
        """Add multiple reasons.

        Args:
            texts: List of reason texts to add.
        """
        for text in texts:
            self.add(text)

    def build(self) -> list[str]:
        """Return a copy of the accumulated reasons.

        Returns:
            List of reason strings.
        """
        return self._reasons.copy()

    def to_string(self) -> str:
        """Join all reasons into a single string.

        Returns:
            Space-separated string of all reasons.
        """
        return " ".join(self._reasons).strip()

    def __len__(self) -> int:
        return len(self._reasons)

    def __bool__(self) -> bool:
        return len(self._reasons) > 0
