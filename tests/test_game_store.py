import re
import threading
import time

import pytest

from game import (
    DuplicateGuessError,
    GameOverError,
    HangmanGame,
    InvalidGuessError,
)
from game_store import GameNotFoundError, GameStore

IDLE_TIMEOUT = 100.0
MISSES_FOR_APPLE = "zxqwvu"


class FakeClock:
    """A clock that only moves when the test advances it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def new_game() -> HangmanGame:
    return HangmanGame("apple", difficulty="easy")


def game_id_of(response: dict[str, object]) -> str:
    return str(response["game_id"])


def read_state(store: GameStore, game_id: str) -> dict[str, object]:
    return store.state(game_id)


def make_guess(store: GameStore, game_id: str) -> dict[str, object]:
    return store.guess(game_id, "z")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(clock: FakeClock) -> GameStore:
    return GameStore(idle_timeout=IDLE_TIMEOUT, clock=clock)


def test_create_returns_id_and_game_state(store):
    response = store.create(new_game())
    game_id = response.pop("game_id")
    assert isinstance(game_id, str)
    assert re.fullmatch(r"[0-9a-f]{32}", game_id)
    assert response == new_game().to_state()


def test_ids_are_unique_and_len_counts_games(store):
    assert len(store) == 0
    ids = {game_id_of(store.create(new_game())) for _ in range(200)}
    assert len(ids) == 200
    assert len(store) == 200


def test_state_returns_the_stored_game(store):
    created = store.create(new_game())
    assert store.state(game_id_of(created)) == created


def test_guess_updates_the_stored_game(store):
    game_id = game_id_of(store.create(new_game()))
    response = store.guess(game_id, "p")
    assert response["pattern"] == "_ p p _ _"
    assert response["guessed_letters"] == ["p"]
    assert store.state(game_id) == response


def test_games_are_independent(store):
    first = game_id_of(store.create(new_game()))
    second = store.create(new_game())
    store.guess(first, "a")
    assert store.state(game_id_of(second)) == second


@pytest.mark.parametrize("access", [read_state, make_guess])
def test_unknown_id_raises_not_found(store, access):
    with pytest.raises(GameNotFoundError) as error:
        access(store, "missing")
    assert str(error.value) == (
        "Game not found. It may have expired, so start a new game."
    )


def test_not_found_is_a_lookup_error():
    assert issubclass(GameNotFoundError, LookupError)


def test_invalid_guess_propagates(store):
    game_id = game_id_of(store.create(new_game()))
    with pytest.raises(InvalidGuessError):
        store.guess(game_id, "1")


def test_duplicate_guess_propagates(store):
    game_id = game_id_of(store.create(new_game()))
    store.guess(game_id, "a")
    with pytest.raises(DuplicateGuessError):
        store.guess(game_id, "a")


def test_guess_after_game_over_propagates(store):
    game_id = game_id_of(store.create(new_game()))
    for letter in MISSES_FOR_APPLE:
        store.guess(game_id, letter)
    with pytest.raises(GameOverError):
        store.guess(game_id, "a")


def test_game_idle_past_timeout_is_removed(store, clock):
    game_id = game_id_of(store.create(new_game()))
    clock.advance(IDLE_TIMEOUT + 1)
    with pytest.raises(GameNotFoundError):
        store.state(game_id)
    assert len(store) == 0


def test_game_idle_exactly_the_timeout_is_kept(store, clock):
    game_id = game_id_of(store.create(new_game()))
    clock.advance(IDLE_TIMEOUT)
    assert store.state(game_id)["game_id"] == game_id


@pytest.mark.parametrize("access", [read_state, make_guess])
def test_access_refreshes_the_idle_timer(store, clock, access):
    game_id = game_id_of(store.create(new_game()))
    clock.advance(60)
    access(store, game_id)
    clock.advance(60)
    assert store.state(game_id)["game_id"] == game_id


def test_expired_game_cannot_be_guessed(store, clock):
    game_id = game_id_of(store.create(new_game()))
    clock.advance(IDLE_TIMEOUT + 1)
    with pytest.raises(GameNotFoundError):
        store.guess(game_id, "a")


def test_create_prunes_expired_games(store, clock):
    store.create(new_game())
    store.create(new_game())
    clock.advance(IDLE_TIMEOUT + 1)
    store.create(new_game())
    assert len(store) == 1


def test_create_prunes_only_the_expired_games(store, clock):
    old = game_id_of(store.create(new_game()))
    clock.advance(60)
    recent = game_id_of(store.create(new_game()))
    clock.advance(50)
    store.create(new_game())
    assert len(store) == 2
    assert store.state(recent)["game_id"] == recent
    with pytest.raises(GameNotFoundError):
        store.state(old)


def test_full_store_evicts_the_oldest_game(clock):
    store = GameStore(max_games=2, clock=clock)
    first = game_id_of(store.create(new_game()))
    second = game_id_of(store.create(new_game()))
    third = game_id_of(store.create(new_game()))
    assert len(store) == 2
    with pytest.raises(GameNotFoundError):
        store.state(first)
    assert store.state(second)["game_id"] == second
    assert store.state(third)["game_id"] == third


def test_access_changes_which_game_is_evicted(clock):
    store = GameStore(max_games=2, clock=clock)
    first = game_id_of(store.create(new_game()))
    second = game_id_of(store.create(new_game()))
    store.state(first)
    third = game_id_of(store.create(new_game()))
    assert len(store) == 2
    with pytest.raises(GameNotFoundError):
        store.state(second)
    assert store.state(first)["game_id"] == first
    assert store.state(third)["game_id"] == third


def test_max_games_must_be_positive():
    with pytest.raises(ValueError):
        GameStore(max_games=0)


def test_concurrent_duplicate_guesses_succeed_once():
    thread_count = 20
    store = GameStore()
    game_id = game_id_of(store.create(new_game()))
    barrier = threading.Barrier(thread_count, timeout=10)
    outcomes: list[Exception | None] = []

    def guess_when_released() -> None:
        barrier.wait()
        try:
            store.guess(game_id, "a")
        except Exception as error:
            outcomes.append(error)
        else:
            outcomes.append(None)

    threads = [
        threading.Thread(target=guess_when_released)
        for _ in range(thread_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    failures = [outcome for outcome in outcomes if outcome is not None]
    assert outcomes.count(None) == 1
    assert len(failures) == thread_count - 1
    assert all(isinstance(f, DuplicateGuessError) for f in failures)
    assert store.state(game_id)["guessed_letters"] == ["a"]


class SlowGame:
    """Stands in for HangmanGame and records overlapping guess calls."""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    def guess(self, letter: object) -> bool:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        time.sleep(0.01)
        self.active -= 1
        return True

    def to_state(self) -> dict[str, object]:
        return {}


def test_store_runs_one_engine_call_at_a_time():
    # The real engine's duplicate check and append are too close together
    # for a missing lock to show up reliably, so a slow stand-in game makes
    # any overlap visible.
    store = GameStore()
    game = SlowGame()
    game_id = store.create(game)["game_id"]
    threads = [
        threading.Thread(target=store.guess, args=(game_id, "a"))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert game.max_active == 1
