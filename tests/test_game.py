import pytest

from game import (
    MAX_INCORRECT_GUESSES,
    DuplicateGuessError,
    GameOverError,
    GameStatus,
    GuessError,
    HangmanGame,
    InvalidGuessError,
    start_game,
)
from word_manager import DIFFICULTIES, InvalidDifficultyError, WordManager

MISSES_FOR_APPLE = "zxqwvu"
WORDS_BY_DIFFICULTY = {
    "easy": "apple",
    "medium": "banana",
    "hard": "pineapple",
}


def play(game: HangmanGame, letters: str) -> None:
    for letter in letters:
        game.guess(letter)


def won_game() -> HangmanGame:
    game = HangmanGame("apple")
    play(game, "aple")
    return game


def lost_game() -> HangmanGame:
    game = HangmanGame("apple")
    play(game, MISSES_FOR_APPLE)
    return game


@pytest.fixture(params=[won_game, lost_game], ids=["won", "lost"])
def finished_game(request) -> HangmanGame:
    return request.param()


def test_initial_state():
    state = HangmanGame("apple", difficulty="easy").to_state()
    assert state == {
        "difficulty": "easy",
        "pattern": "_ _ _ _ _",
        "guessed_letters": [],
        "incorrect_letters": [],
        "remaining_guesses": 6,
        "max_incorrect_guesses": 6,
        "status": "playing",
    }
    assert "word" not in state


def test_difficulty_defaults_to_none():
    game = HangmanGame("apple")
    assert game.difficulty is None
    assert game.to_state()["difficulty"] is None


def test_initial_properties():
    game = HangmanGame("apple", difficulty="medium")
    assert game.difficulty == "medium"
    assert game.max_incorrect_guesses == MAX_INCORRECT_GUESSES == 6
    assert game.guessed_letters == ()
    assert game.correct_letters == ()
    assert game.incorrect_letters == ()
    assert game.remaining_guesses == 6
    assert game.status is GameStatus.PLAYING
    assert not game.is_over


def test_status_values_are_plain_strings():
    assert GameStatus.PLAYING == "playing"
    assert GameStatus.WON == "won"
    assert GameStatus.LOST == "lost"


def test_correct_guess_reveals_every_occurrence():
    game = HangmanGame("apple")
    assert game.guess("p") is True
    assert game.pattern == "_ p p _ _"
    assert game.remaining_guesses == 6
    assert game.correct_letters == ("p",)
    assert game.incorrect_letters == ()


def test_incorrect_guess_costs_a_guess():
    game = HangmanGame("apple")
    assert game.guess("z") is False
    assert game.pattern == "_ _ _ _ _"
    assert game.remaining_guesses == 5
    assert game.incorrect_letters == ("z",)
    assert game.to_state()["incorrect_letters"] == ["z"]


def test_letters_keep_guess_order_across_correct_and_incorrect():
    game = HangmanGame("apple")
    play(game, "zaqp")
    assert game.guessed_letters == ("z", "a", "q", "p")
    assert game.correct_letters == ("a", "p")
    assert game.incorrect_letters == ("z", "q")
    assert game.to_state()["guessed_letters"] == ["z", "a", "q", "p"]


def test_uppercase_correct_guess_is_stored_lowercase():
    game = HangmanGame("apple")
    assert game.guess("P") is True
    assert game.guessed_letters == ("p",)
    assert game.pattern == "_ p p _ _"


def test_uppercase_incorrect_guess_is_stored_lowercase():
    game = HangmanGame("apple")
    assert game.guess("Z") is False
    assert game.incorrect_letters == ("z",)


@pytest.mark.parametrize(
    "bad_guess", ["", "ab", "1", " ", " e", "é", "-", None, 5, ["a"]]
)
def test_invalid_guess_raises_and_changes_nothing(bad_guess):
    game = HangmanGame("apple")
    play(game, "az")
    before = game.to_state()
    with pytest.raises(InvalidGuessError, match="single letter"):
        game.guess(bad_guess)
    assert game.to_state() == before


@pytest.mark.parametrize("letters", ["aa", "zz", "aA", "Aa"])
def test_duplicate_guess_raises_and_changes_nothing(letters):
    game = HangmanGame("apple")
    game.guess(letters[0])
    before = game.to_state()
    with pytest.raises(DuplicateGuessError, match="already guessed"):
        game.guess(letters[1])
    assert game.to_state() == before
    assert game.remaining_guesses == before["remaining_guesses"]


def test_duplicate_message_names_the_letter():
    game = HangmanGame("apple")
    game.guess("e")
    with pytest.raises(DuplicateGuessError) as error:
        game.guess("E")
    assert str(error.value) == "You already guessed 'e'."


def test_guess_errors_share_a_base_class():
    for error in (InvalidGuessError, DuplicateGuessError, GameOverError):
        assert issubclass(error, GuessError)


def test_win_without_misses():
    game = HangmanGame("apple")
    play(game, "aple")
    state = game.to_state()
    assert game.status is GameStatus.WON
    assert game.is_over
    assert state["status"] == "won"
    assert state["word"] == "apple"
    assert state["pattern"] == "a p p l e"
    assert state["remaining_guesses"] == 6


def test_win_with_misses():
    game = HangmanGame("banana")
    play(game, "zbxan")
    state = game.to_state()
    assert game.status is GameStatus.WON
    assert state["word"] == "banana"
    assert state["pattern"] == "b a n a n a"
    assert state["incorrect_letters"] == ["z", "x"]
    assert state["remaining_guesses"] == 4


def test_loss_after_sixth_miss():
    game = HangmanGame("apple")
    play(game, MISSES_FOR_APPLE[:5])
    assert game.status is GameStatus.PLAYING
    assert game.remaining_guesses == 1
    assert "word" not in game.to_state()

    game.guess(MISSES_FOR_APPLE[5])
    state = game.to_state()
    assert game.status is GameStatus.LOST
    assert game.is_over
    assert game.remaining_guesses == 0
    assert state["status"] == "lost"
    assert state["remaining_guesses"] == 0
    assert state["word"] == "apple"


def test_loss_keeps_unguessed_letters_masked_in_pattern():
    game = HangmanGame("apple")
    play(game, "a" + MISSES_FOR_APPLE)
    assert game.status is GameStatus.LOST
    assert game.pattern == "a _ _ _ _"


def test_guess_after_game_over_raises(finished_game):
    before = finished_game.to_state()
    with pytest.raises(GameOverError, match="Start a new game"):
        finished_game.guess("k")
    assert finished_game.to_state() == before


def test_duplicate_guess_after_game_over_raises_game_over(finished_game):
    repeated = finished_game.guessed_letters[0]
    with pytest.raises(GameOverError):
        finished_game.guess(repeated)


def test_invalid_guess_after_game_over_raises_invalid_guess(finished_game):
    before = finished_game.to_state()
    with pytest.raises(InvalidGuessError):
        finished_game.guess("1")
    assert finished_game.to_state() == before


def test_word_is_never_in_state_until_game_ends():
    game = HangmanGame("banana")
    assert "word" not in game.to_state()
    for letter in "zbxan":
        assert "word" not in game.to_state()
        game.guess(letter)
    assert game.to_state()["word"] == "banana"


def test_repr_does_not_reveal_the_word():
    game = HangmanGame("banana", difficulty="medium")
    game.guess("z")
    text = repr(game)
    assert "banana" not in text
    assert "medium" in text
    assert "_ _ _ _ _ _" in text
    assert "playing" in text


def test_game_has_no_public_word_accessor():
    game = HangmanGame("banana")
    assert not hasattr(game, "word")


def test_properties_are_read_only():
    game = HangmanGame("apple")
    with pytest.raises(AttributeError):
        game.pattern = "a p p l e"
    with pytest.raises(AttributeError):
        game.status = GameStatus.WON


def test_to_state_returns_fresh_lists():
    game = HangmanGame("apple")
    play(game, "az")
    state = game.to_state()
    state["guessed_letters"].append("q")
    state["incorrect_letters"].clear()
    assert game.guessed_letters == ("a", "z")
    assert game.incorrect_letters == ("z",)
    assert game.to_state()["guessed_letters"] == ["a", "z"]


def test_to_state_has_exactly_the_documented_keys():
    state = HangmanGame("apple").to_state()
    assert set(state) == {
        "difficulty",
        "pattern",
        "guessed_letters",
        "incorrect_letters",
        "remaining_guesses",
        "max_incorrect_guesses",
        "status",
    }


@pytest.mark.parametrize(
    "bad_word", ["", "ab1", "naïve", "two words", None, 5]
)
def test_constructor_rejects_invalid_word(bad_word):
    with pytest.raises(ValueError):
        HangmanGame(bad_word)


def test_constructor_stores_word_lowercase():
    game = HangmanGame("APPLE")
    assert game.guess("a") is True
    assert game.pattern == "a _ _ _ _"
    play(game, "ple")
    assert game.to_state()["word"] == "apple"


@pytest.mark.parametrize("bad_max", [0, -1, True, False, 2.5, "3", None])
def test_constructor_rejects_invalid_max_incorrect_guesses(bad_max):
    with pytest.raises(ValueError):
        HangmanGame("apple", max_incorrect_guesses=bad_max)


def test_custom_max_incorrect_guesses_loses_after_that_many_misses():
    game = HangmanGame("apple", max_incorrect_guesses=3)
    assert game.max_incorrect_guesses == 3
    play(game, "zx")
    assert game.status is GameStatus.PLAYING
    assert game.remaining_guesses == 1
    game.guess("q")
    assert game.status is GameStatus.LOST
    state = game.to_state()
    assert state["max_incorrect_guesses"] == 3
    assert state["remaining_guesses"] == 0


@pytest.fixture
def word_manager() -> WordManager:
    return WordManager({d: [w] for d, w in WORDS_BY_DIFFICULTY.items()})


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_start_game_for_each_difficulty(word_manager, difficulty):
    word = WORDS_BY_DIFFICULTY[difficulty]
    game = start_game(word_manager, difficulty)
    assert game.difficulty == difficulty
    assert game.pattern == " ".join("_" * len(word))
    assert game.status is GameStatus.PLAYING
    state = game.to_state()
    assert state["difficulty"] == difficulty
    assert "word" not in state


def test_start_game_normalizes_difficulty(word_manager):
    game = start_game(word_manager, " Medium ")
    assert game.difficulty == "medium"
    assert game.pattern == "_ _ _ _ _ _"


@pytest.mark.parametrize("bad_difficulty", ["expert", "", None, 5, ["easy"]])
def test_start_game_rejects_invalid_difficulty(word_manager, bad_difficulty):
    with pytest.raises(InvalidDifficultyError):
        start_game(word_manager, bad_difficulty)


def test_constructor_normalizes_difficulty():
    assert HangmanGame("apple", difficulty=" Easy ").difficulty == "easy"


@pytest.mark.parametrize("bad_difficulty", ["expert", "", 5])
def test_constructor_rejects_invalid_difficulty(bad_difficulty):
    with pytest.raises(InvalidDifficultyError):
        HangmanGame("apple", difficulty=bad_difficulty)


def test_new_game_after_finished_game(word_manager, finished_game):
    new_game = start_game(word_manager, "easy")
    assert new_game.status is GameStatus.PLAYING
    assert new_game.guessed_letters == ()
    assert new_game.remaining_guesses == MAX_INCORRECT_GUESSES
    assert new_game.guess("a") is True
    with pytest.raises(GameOverError):
        finished_game.guess("k")


def test_word_matching_its_difficulty_name_reveals_nothing():
    # "easy" is a real Easy word, so the difficulty field matches the word
    # text. The state is still identical to any other 4-letter Easy word.
    tricky = HangmanGame("easy", difficulty="easy")
    other = HangmanGame("fish", difficulty="easy")
    assert tricky.to_state() == other.to_state()
    assert repr(tricky) == repr(other)
    tricky.guess("z")
    other.guess("z")
    assert tricky.to_state() == other.to_state()
