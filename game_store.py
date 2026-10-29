"""Thread-safe in-memory storage for active Hangman games."""

import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from game import HangmanGame


class GameNotFoundError(LookupError):
    """Raised when a game ID is unknown or its game has expired."""

    def __init__(self) -> None:
        super().__init__(
            "Game not found. It may have expired, so start a new game."
        )


@dataclass
class _Entry:
    game: HangmanGame
    last_used: float


def _response(game_id: str, game: HangmanGame) -> dict[str, object]:
    return {"game_id": game_id, **game.to_state()}


class GameStore:
    """Active games by ID, with idle expiry and a cap on stored games.

    One lock is held for the whole of every public method, including the
    engine call, so two requests cannot both pass the engine's duplicate
    guess check on the same game.
    """

    def __init__(
        self,
        *,
        idle_timeout: float = 3600.0,
        max_games: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_games < 1:
            raise ValueError("max_games must be at least 1.")
        self._idle_timeout = idle_timeout
        self._max_games = max_games
        self._clock = clock
        # Least recently used first, so expiry and eviction only ever
        # look at the front of the dict.
        self._games: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._games)

    def create(self, game: HangmanGame) -> dict[str, object]:
        """Store a new game under a fresh ID and return its response."""
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            while len(self._games) >= self._max_games:
                self._games.popitem(last=False)
            game_id = uuid.uuid4().hex
            self._games[game_id] = _Entry(game, now)
            return _response(game_id, game)

    def state(self, game_id: str) -> dict[str, object]:
        """Return the response for a game, or raise GameNotFoundError."""
        with self._lock:
            game = self._use(game_id)
            return _response(game_id, game)

    def guess(self, game_id: str, letter: object) -> dict[str, object]:
        """Apply a guess and return the response.

        Engine errors (invalid, duplicate or after the game is over)
        propagate unchanged.
        """
        with self._lock:
            game = self._use(game_id)
            game.guess(letter)
            return _response(game_id, game)

    def _is_expired(self, entry: _Entry, now: float) -> bool:
        return now - entry.last_used > self._idle_timeout

    def _prune_expired(self, now: float) -> None:
        while self._games:
            oldest = next(iter(self._games.values()))
            if not self._is_expired(oldest, now):
                return
            self._games.popitem(last=False)

    def _use(self, game_id: str) -> HangmanGame:
        """Return a live game and mark it as the most recently used."""
        now = self._clock()
        entry = self._games.get(game_id)
        if entry is None:
            raise GameNotFoundError()
        if self._is_expired(entry, now):
            del self._games[game_id]
            raise GameNotFoundError()
        entry.last_used = now
        self._games.move_to_end(game_id)
        return entry.game
