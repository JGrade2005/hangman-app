"""Hangman game engine. Pure Python, no web or UI dependencies."""

from enum import StrEnum

from word_manager import WordManager, normalize_difficulty

MAX_INCORRECT_GUESSES = 6


class GameStatus(StrEnum):
    """Lifecycle state of a game."""

    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class GuessError(Exception):
    """Base class for guesses the game refuses."""


class InvalidGuessError(GuessError):
    """Raised when a guess is not a single letter from A to Z."""


class DuplicateGuessError(GuessError):
    """Raised when a letter has already been guessed."""


class GameOverError(GuessError):
    """Raised when a guess is made after the game has ended."""


def _is_ascii_letters(text: str) -> bool:
    return text.isascii() and text.isalpha()


def _normalize_letter(letter: object) -> str:
    if isinstance(letter, str) and len(letter) == 1:
        if _is_ascii_letters(letter):
            return letter.lower()
    raise InvalidGuessError("Guess a single letter from A to Z.")


class HangmanGame:
    """One game of Hangman.

    A plain class rather than a dataclass so the generated repr cannot
    leak the hidden word into logs.
    """

    def __init__(
        self,
        word: str,
        *,
        difficulty: str | None = None,
        max_incorrect_guesses: int = MAX_INCORRECT_GUESSES,
    ):
        if not (isinstance(word, str) and _is_ascii_letters(word)):
            raise ValueError("word must be non-empty ASCII letters.")
        if (
            isinstance(max_incorrect_guesses, bool)
            or not isinstance(max_incorrect_guesses, int)
            or max_incorrect_guesses < 1
        ):
            raise ValueError("max_incorrect_guesses must be an integer >= 1.")
        self._word = word.lower()
        self._difficulty = (
            None if difficulty is None else normalize_difficulty(difficulty)
        )
        self._max_incorrect_guesses = max_incorrect_guesses
        self._guessed: list[str] = []

    def __repr__(self) -> str:
        return (
            f"HangmanGame(difficulty={self._difficulty!r}, "
            f"pattern={self.pattern!r}, status={self.status.value!r})"
        )

    @property
    def difficulty(self) -> str | None:
        """Difficulty the game was started with, if any."""
        return self._difficulty

    @property
    def max_incorrect_guesses(self) -> int:
        """Number of incorrect guesses that ends the game."""
        return self._max_incorrect_guesses

    @property
    def guessed_letters(self) -> tuple[str, ...]:
        """Every accepted guess, in guess order."""
        return tuple(self._guessed)

    @property
    def correct_letters(self) -> tuple[str, ...]:
        """Guessed letters that are in the word, in guess order."""
        return tuple(c for c in self._guessed if c in self._word)

    @property
    def incorrect_letters(self) -> tuple[str, ...]:
        """Guessed letters that are not in the word, in guess order."""
        return tuple(c for c in self._guessed if c not in self._word)

    @property
    def remaining_guesses(self) -> int:
        """Incorrect guesses left before the game is lost."""
        return self._max_incorrect_guesses - len(self.incorrect_letters)

    @property
    def pattern(self) -> str:
        """The word with unguessed letters masked, e.g. `_ p p _ _`."""
        return " ".join(c if c in self._guessed else "_" for c in self._word)

    @property
    def status(self) -> GameStatus:
        """Current status, computed from the guesses made."""
        if all(c in self._guessed for c in self._word):
            return GameStatus.WON
        if self.remaining_guesses == 0:
            return GameStatus.LOST
        return GameStatus.PLAYING

    @property
    def is_over(self) -> bool:
        """True once the game is won or lost."""
        return self.status is not GameStatus.PLAYING

    def guess(self, letter: object) -> bool:
        """Record a guess and return True if the letter is in the word.

        Raises InvalidGuessError, GameOverError or DuplicateGuessError, in
        that order of precedence, without changing any state.
        """
        normalized = _normalize_letter(letter)
        if self.is_over:
            raise GameOverError("This game is over. Start a new game.")
        if normalized in self._guessed:
            raise DuplicateGuessError(f"You already guessed '{normalized}'.")
        self._guessed.append(normalized)
        return normalized in self._word

    def to_state(self) -> dict[str, object]:
        """Return a JSON-ready snapshot that is safe to send to a client.

        The word is included only once the game is over.
        """
        status = self.status
        state: dict[str, object] = {
            "difficulty": self._difficulty,
            "pattern": self.pattern,
            "guessed_letters": list(self.guessed_letters),
            "incorrect_letters": list(self.incorrect_letters),
            "remaining_guesses": self.remaining_guesses,
            "max_incorrect_guesses": self._max_incorrect_guesses,
            "status": status.value,
        }
        if status is not GameStatus.PLAYING:
            state["word"] = self._word
        return state


def start_game(words: WordManager, difficulty: object) -> HangmanGame:
    """Start a game with a random word of the requested difficulty."""
    normalized = normalize_difficulty(difficulty)
    return HangmanGame(words.random_word(normalized), difficulty=normalized)
