"""Word lists grouped by difficulty, with loading, cleaning and selection."""

import logging
import secrets
from collections.abc import Iterable, Mapping
from pathlib import Path

DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")
DEFAULT_WORDS_DIR = Path(__file__).parent / "words"

logger = logging.getLogger(__name__)


class InvalidDifficultyError(ValueError):
    """Raised when a value is not one of the supported difficulties."""


def normalize_difficulty(value: object) -> str:
    """Return the lowercase, stripped difficulty or raise if it is invalid."""
    if isinstance(value, str):
        difficulty = value.strip().lower()
        if difficulty in DIFFICULTIES:
            return difficulty
    raise InvalidDifficultyError(
        f"Difficulty must be one of: {', '.join(DIFFICULTIES)}."
    )


def clean_words(raw_words: Iterable[str]) -> tuple[str, ...]:
    """Return unique lowercase ASCII-letter words in first-seen order.

    Blank entries are skipped silently. Other invalid entries are skipped
    with a logged warning.
    """
    # A dict is an ordered set: re-assigning a key keeps its first position.
    words: dict[str, None] = {}
    for raw in raw_words:
        entry = raw.strip()
        if not entry:
            continue
        if not (entry.isascii() and entry.isalpha()):
            logger.warning("Skipping invalid word %r", raw)
            continue
        words[entry.lower()] = None
    return tuple(words)


class WordManager:
    """Holds the cleaned word list for each difficulty."""

    def __init__(self, words_by_difficulty: Mapping[str, Iterable[str]]):
        unknown = [d for d in words_by_difficulty if d not in DIFFICULTIES]
        if unknown:
            raise ValueError(
                f"Unknown difficulties: {', '.join(map(str, unknown))}."
            )
        self._words: dict[str, tuple[str, ...]] = {
            difficulty: self._clean_list(difficulty, words_by_difficulty)
            for difficulty in DIFFICULTIES
        }

    @staticmethod
    def _clean_list(
        difficulty: str, words_by_difficulty: Mapping[str, Iterable[str]]
    ) -> tuple[str, ...]:
        if difficulty not in words_by_difficulty:
            raise ValueError(f"Missing word list for '{difficulty}'.")
        raw_words = words_by_difficulty[difficulty]
        # A bare string is iterable, so it would load as single letters.
        if isinstance(raw_words, str):
            raise TypeError(
                f"Word list for '{difficulty}' must be a list, not a string."
            )
        cleaned = clean_words(raw_words)
        if not cleaned:
            raise ValueError(
                f"Word list for '{difficulty}' has no valid words."
            )
        return cleaned

    @classmethod
    def from_directory(
        cls, directory: Path = DEFAULT_WORDS_DIR
    ) -> "WordManager":
        """Load `<directory>/<difficulty>.txt` for every difficulty."""
        return cls(
            {
                # utf-8-sig drops the BOM some Windows editors add, which
                # would otherwise make the first word invalid.
                difficulty: (directory / f"{difficulty}.txt")
                .read_text(encoding="utf-8-sig")
                .splitlines()
                for difficulty in DIFFICULTIES
            }
        )

    def words(self, difficulty: str) -> tuple[str, ...]:
        """Return the word list for a difficulty."""
        return self._words[normalize_difficulty(difficulty)]

    def random_word(self, difficulty: str) -> str:
        """Return a random word for a difficulty."""
        # secrets, not random: a seeded generator must not predict the word.
        return secrets.choice(self.words(difficulty))
