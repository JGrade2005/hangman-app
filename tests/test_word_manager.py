import logging
from pathlib import Path

import pytest

from word_manager import (
    DEFAULT_WORDS_DIR,
    DIFFICULTIES,
    InvalidDifficultyError,
    WordManager,
    clean_words,
    normalize_difficulty,
)

SAMPLE_WORDS = {
    "easy": ["cat", "dog"],
    "medium": ["planet", "garden"],
    "hard": ["labyrinth", "rhapsody"],
}


@pytest.fixture(scope="module")
def real_manager() -> WordManager:
    return WordManager.from_directory()


@pytest.fixture
def manager() -> WordManager:
    return WordManager(SAMPLE_WORDS)


def write_word_files(directory: Path, difficulties=DIFFICULTIES) -> None:
    for difficulty in difficulties:
        words = SAMPLE_WORDS[difficulty]
        (directory / f"{difficulty}.txt").write_text(
            "\n".join(words) + "\n", encoding="utf-8"
        )


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_word_lists_are_not_empty(real_manager, difficulty):
    assert len(real_manager.words(difficulty)) > 0


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_words_are_lowercase_ascii_letters(real_manager, difficulty):
    for word in real_manager.words(difficulty):
        assert word.isascii() and word.isalpha() and word == word.lower()


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_words_have_no_duplicates(real_manager, difficulty):
    words = real_manager.words(difficulty)
    assert len(words) == len(set(words))


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_files_lose_no_lines_when_cleaned(real_manager, difficulty):
    lines = (DEFAULT_WORDS_DIR / f"{difficulty}.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    non_blank = [line for line in lines if line.strip()]
    assert len(real_manager.words(difficulty)) == len(non_blank)


def test_clean_words_strips_and_lowercases():
    assert clean_words(["  Apple ", "BANANA", "cherry\n"]) == (
        "apple",
        "banana",
        "cherry",
    )


def test_clean_words_skips_blank_entries_silently(caplog):
    with caplog.at_level(logging.WARNING, logger="word_manager"):
        assert clean_words(["", "   ", "\t", "ok"]) == ("ok",)
    assert caplog.records == []


@pytest.mark.parametrize(
    "invalid", ["ca-t", "naïve", "123", "two words", "a1"]
)
def test_clean_words_skips_and_warns_for_invalid_entries(caplog, invalid):
    with caplog.at_level(logging.WARNING, logger="word_manager"):
        assert clean_words([invalid, "valid"]) == ("valid",)
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert repr(invalid) in caplog.records[0].getMessage()


def test_clean_words_logs_one_warning_per_invalid_entry(caplog):
    with caplog.at_level(logging.WARNING, logger="word_manager"):
        result = clean_words(["ca-t", "naïve", "123", "dog"])
    assert result == ("dog",)
    assert len(caplog.records) == 3


def test_clean_words_removes_duplicates_case_insensitively():
    result = clean_words(["Apple", "apple", "APPLE", "pear"])
    assert result == ("apple", "pear")


def test_clean_words_keeps_first_seen_order():
    assert clean_words(["pear", "apple", "Pear", "fig", "apple"]) == (
        "pear",
        "apple",
        "fig",
    )


def test_clean_words_accepts_any_iterable():
    assert clean_words(word for word in ["a", "b", "a"]) == ("a", "b")


def test_manager_cleans_each_list():
    manager = WordManager(
        {
            "easy": ["Cat", "cat", "d-og"],
            "medium": [" planet "],
            "hard": ["labyrinth"],
        }
    )
    assert manager.words("easy") == ("cat",)
    assert manager.words("medium") == ("planet",)


def test_manager_rejects_missing_difficulty():
    words = {k: v for k, v in SAMPLE_WORDS.items() if k != "hard"}
    with pytest.raises(ValueError, match="hard"):
        WordManager(words)


def test_manager_rejects_unknown_difficulty():
    with pytest.raises(ValueError, match="expert"):
        WordManager({**SAMPLE_WORDS, "expert": ["xylophone"]})


@pytest.mark.parametrize("raw", [[], ["", "   "], ["ca-t", "123"]])
def test_manager_rejects_list_empty_after_cleaning(raw):
    with pytest.raises(ValueError, match="medium"):
        WordManager({**SAMPLE_WORDS, "medium": raw})


def test_from_directory_loads_every_difficulty(tmp_path):
    write_word_files(tmp_path)
    manager = WordManager.from_directory(tmp_path)
    for difficulty in DIFFICULTIES:
        assert manager.words(difficulty) == tuple(SAMPLE_WORDS[difficulty])


def test_from_directory_missing_file_raises(tmp_path):
    write_word_files(tmp_path, difficulties=("easy", "medium"))
    with pytest.raises(FileNotFoundError):
        WordManager.from_directory(tmp_path)


def test_from_directory_empty_file_raises_value_error(tmp_path):
    write_word_files(tmp_path)
    (tmp_path / "hard.txt").write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hard"):
        WordManager.from_directory(tmp_path)


def test_words_returns_immutable_tuple(manager):
    assert isinstance(manager.words("easy"), tuple)


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_random_word_comes_from_that_difficulty(manager, difficulty):
    for _ in range(20):
        assert manager.random_word(difficulty) in SAMPLE_WORDS[difficulty]


@pytest.mark.parametrize(
    ("variant", "difficulty"),
    [
        ("EASY", "easy"),
        (" Medium ", "medium"),
        ("\tHARD\n", "hard"),
        ("eAsY", "easy"),
    ],
)
def test_random_word_accepts_case_and_whitespace_variants(
    manager, variant, difficulty
):
    assert manager.random_word(variant) in SAMPLE_WORDS[difficulty]
    assert manager.words(variant) == tuple(SAMPLE_WORDS[difficulty])


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_random_word_from_real_lists_varies(real_manager, difficulty):
    drawn = {real_manager.random_word(difficulty) for _ in range(50)}
    assert len(drawn) > 1
    assert drawn <= set(real_manager.words(difficulty))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("easy", "easy"),
        ("EASY", "easy"),
        (" Medium ", "medium"),
        ("\tHard\n", "hard"),
    ],
)
def test_normalize_difficulty_accepts_valid_values(value, expected):
    assert normalize_difficulty(value) == expected


INVALID_DIFFICULTIES = ["expert", "", "   ", None, 5, ["easy"]]


@pytest.mark.parametrize("value", INVALID_DIFFICULTIES)
def test_normalize_difficulty_rejects_invalid_values(value):
    with pytest.raises(InvalidDifficultyError, match="easy, medium, hard"):
        normalize_difficulty(value)


@pytest.mark.parametrize("value", INVALID_DIFFICULTIES)
def test_manager_rejects_invalid_difficulty(manager, value):
    with pytest.raises(InvalidDifficultyError):
        manager.random_word(value)
    with pytest.raises(InvalidDifficultyError):
        manager.words(value)


def test_invalid_difficulty_error_is_a_value_error():
    assert issubclass(InvalidDifficultyError, ValueError)


def test_manager_rejects_bare_string_word_list():
    with pytest.raises(TypeError, match="easy"):
        WordManager({**SAMPLE_WORDS, "easy": "cat"})


def test_from_directory_ignores_bom_and_crlf(tmp_path):
    write_word_files(tmp_path)
    (tmp_path / "easy.txt").write_bytes("﻿cat\r\ndog\r\n".encode())
    manager = WordManager.from_directory(tmp_path)
    assert manager.words("easy") == ("cat", "dog")
