"""End-to-end tests that drive the Hangman page in headless Chromium.

Install the browser once with `python -m playwright install chromium`, or
leave these tests out with `pytest -m "not ui"`.

Waits use expect() assertions only. The server sends a Content-Security-
Policy without 'unsafe-eval', so page.wait_for_function cannot run.
"""

import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from urllib.parse import urlparse

import pytest
from flask import request
from werkzeug.serving import make_server

from game_store import GameStore
from server import app as shipped_app
from server import create_app
from word_manager import DIFFICULTIES, WordManager

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import (  # noqa: E402
    Browser,
    ConsoleMessage,
    Locator,
    Page,
    Request,
    Response,
    expect,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError  # noqa: E402

pytestmark = pytest.mark.ui

WORDS = {"easy": "apple", "medium": "banana", "hard": "questionable"}
WORD_LISTS = {difficulty: [word] for difficulty, word in WORDS.items()}
IDLE_TIMEOUT = 60.0
SLOW_GUESS_SECONDS = 0.8
SETTLE_MS = 200
# A short poll keeps server.shutdown() from waiting half a second per test.
SERVER_POLL_SECONDS = 0.02
MAX_MISSES = 6
# None of these letters is in any of the words above.
MISSES = "zxwvkj"
API_PREFIX = "/api/"
NO_CHROMIUM = (
    "Chromium could not be launched: run `python -m playwright install "
    "chromium`."
)
STARTED = "New game started. Guess a letter."
EXPIRED = "This game has expired. Press New game to start another."
UNREACHABLE = (
    "Could not reach the server. Check your connection and try again."
)
PLAYING_KEYS = {
    "game_id",
    "difficulty",
    "pattern",
    "guessed_letters",
    "incorrect_letters",
    "remaining_guesses",
    "max_incorrect_guesses",
    "status",
}


class FakeClock:
    """A clock that only moves when a test advances it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class GuessLatency:
    """Server-side delay for guess requests.

    The delay lives in the server because sleeping in a Playwright route
    handler would block Playwright itself, so the page would never see
    any latency.
    """

    def __init__(self) -> None:
        self.seconds = 0.0

    def apply(self) -> None:
        if request.path.endswith("/guess"):
            time.sleep(self.seconds)


@dataclass
class LiveServer:
    url: str
    clock: FakeClock
    latency: GuessLatency


class PageWatch:
    """Records the API traffic and the errors of one page."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.api_requests: list[str] = []
        self.api_responses: list[Response] = []
        self.page_errors: list[str] = []
        self.console_errors: list[str] = []
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("pageerror", self._on_page_error)
        page.on("console", self._on_console)

    @property
    def guess_requests(self) -> list[str]:
        return [line for line in self.api_requests if line.endswith("/guess")]

    def api_bodies(self) -> list[dict[str, object]]:
        # Bodies are read lazily: the response event fires before the page
        # can render the reply, so every reply it showed is already listed.
        return [response.json() for response in self.api_responses]

    def assert_no_leaks(self) -> None:
        playing = [
            body
            for body in self.api_bodies()
            if body.get("status") == "playing"
        ]
        assert playing, "no playing response was recorded"
        for body in playing:
            assert "word" not in body
            assert set(body) == PLAYING_KEYS

    def assert_no_page_errors(self) -> None:
        assert self.page_errors == []

    def assert_clean(self) -> None:
        self.assert_no_leaks()
        self.assert_no_page_errors()
        assert self.console_errors == []

    def _on_request(self, sent: Request) -> None:
        path = urlparse(sent.url).path
        if path.startswith(API_PREFIX):
            self.api_requests.append(f"{sent.method} {path}")

    def _on_response(self, received: Response) -> None:
        if urlparse(received.url).path.startswith(API_PREFIX):
            self.api_responses.append(received)

    def _on_page_error(self, error: Exception) -> None:
        self.page_errors.append(str(error))

    def _on_console(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch()
        except PlaywrightError:
            pytest.skip(NO_CHROMIUM)
        yield chromium
        chromium.close()


@pytest.fixture
def live() -> Iterator[LiveServer]:
    clock = FakeClock()
    latency = GuessLatency()
    store = GameStore(idle_timeout=IDLE_TIMEOUT, clock=clock)
    app = create_app(WordManager(WORD_LISTS), store=store)
    app.before_request(latency.apply)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": SERVER_POLL_SECONDS},
        daemon=True,
    )
    thread.start()
    yield LiveServer(f"http://127.0.0.1:{server.server_port}", clock, latency)
    server.shutdown()
    thread.join()
    server.server_close()


@pytest.fixture(scope="module")
def shipped_url() -> Iterator[str]:
    server = make_server("127.0.0.1", 0, shipped_app, threaded=True)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": SERVER_POLL_SECONDS},
        daemon=True,
    )
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()
    server.server_close()


@pytest.fixture
def watch(browser: Browser, live: LiveServer) -> Iterator[PageWatch]:
    context = browser.new_context()
    recorder = PageWatch(context.new_page())
    recorder.page.goto(live.url)
    yield recorder
    context.close()


@pytest.fixture
def page(watch: PageWatch) -> Page:
    return watch.page


def key_for(page: Page, letter: str) -> Locator:
    return page.locator(f'#keyboard .key[data-letter="{letter}"]')


def start_game(page: Page, difficulty: str) -> None:
    page.select_option("#difficulty", difficulty)
    page.click("#new-game")
    expect_message(page, STARTED)


def guess_by_click(page: Page, letter: str) -> None:
    key_for(page, letter).click()


def guess_by_key(page: Page, letter: str) -> None:
    page.keyboard.press(letter)


def type_letters(page: Page, letters: str) -> None:
    """Type letters one at a time: the page ignores keys during a guess."""
    for letter in letters:
        guess_by_key(page, letter)
        expect(key_for(page, letter)).to_be_disabled()


def settle(page: Page) -> None:
    # Only for asserting that nothing happens: there is no state to wait for.
    page.wait_for_timeout(SETTLE_MS)


def distinct_letters(word: str) -> str:
    return "".join(dict.fromkeys(word))


def format_letters(letters: str) -> str:
    return ", ".join(letters.upper()) or "None yet"


def remaining_text(misses: int) -> str:
    return f"Incorrect guesses left: {MAX_MISSES - misses} of {MAX_MISSES}"


def won_message(word: str) -> str:
    return f"You won! The word was {word.upper()}."


def lost_message(word: str) -> str:
    return f"Out of guesses. The word was {word.upper()}."


def guess_message(word: str, guessed: str) -> str:
    letter = guessed[-1]
    if set(word) <= set(guessed):
        return won_message(word)
    if sum(c not in word for c in guessed) == MAX_MISSES:
        return lost_message(word)
    if letter in word:
        return f"Yes, {letter.upper()} is in the word."
    return f"No, {letter.upper()} is not in the word."


def expect_text(page: Page, selector: str, text: str) -> None:
    expect(page.locator(selector)).to_have_text(text)


def expect_message(page: Page, text: str) -> None:
    expect_text(page, "#message", text)


def expect_parts(page: Page, count: int) -> None:
    expect(page.locator("#drawing .part.shown")).to_have_count(count)


def expect_enabled_keys(page: Page, count: int) -> None:
    expect(page.locator("#keyboard .key:not([disabled])")).to_have_count(
        count
    )


def expect_word(page: Page, shown: str) -> None:
    """Check the cells and the label; `_` in `shown` is a blank cell."""
    cells = ["" if c == "_" else c for c in shown]
    spoken = ["blank" if c == "_" else c for c in shown]
    expect(page.locator("#word .cell")).to_have_text(cells)
    expect(page.locator("#word")).to_have_attribute(
        "aria-label", f"Word: {' '.join(spoken)}"
    )


def expect_after_guess(page: Page, word: str, guessed: str) -> None:
    letter = guessed[-1]
    misses = "".join(c for c in guessed if c not in word)
    key = key_for(page, letter)
    expect(key).to_be_disabled()
    expect(key).to_have_class(
        "key correct" if letter in word else "key incorrect"
    )
    expect_message(page, guess_message(word, guessed))
    expect_parts(page, len(misses))
    expect_text(page, "#remaining", remaining_text(len(misses)))
    expect_text(page, "#guessed-letters", format_letters(guessed))
    expect_text(page, "#incorrect-letters", format_letters(misses))


def expect_revealed_loss(page: Page, word: str, guessed: str) -> None:
    cells = page.locator("#word .cell")
    missed = [letter not in guessed for letter in word]
    spoken = [
        f"{letter.upper()} (missed)" if is_missed else letter.upper()
        for letter, is_missed in zip(word, missed, strict=True)
    ]
    expect(cells).to_have_text(list(word.upper()))
    for index, is_missed in enumerate(missed):
        expect(cells.nth(index)).to_have_class(
            "cell missed" if is_missed else "cell"
        )
    expect(page.locator("#word")).to_have_attribute(
        "aria-label", f"Word: {' '.join(spoken)}"
    )


def play_and_check(
    page: Page,
    word: str,
    letters: str,
    guess: Callable[[Page, str], None],
) -> None:
    guessed = ""
    for letter in letters:
        guess(page, letter)
        guessed += letter
        expect_after_guess(page, word, guessed)


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_win_by_clicking_keys(page, watch, difficulty):
    word = WORDS[difficulty]
    start_game(page, difficulty)
    play_and_check(page, word, "z" + distinct_letters(word), guess_by_click)

    expect(page.locator("#message")).to_have_class("win")
    expect_word(page, word.upper())
    expect_enabled_keys(page, 0)
    expect(page.locator("#new-game")).to_be_focused()
    watch.assert_clean()


@pytest.mark.parametrize(
    ("difficulty", "hit"), [("easy", "p"), ("medium", "n"), ("hard", "e")]
)
def test_loss_by_typing_letters(page, watch, difficulty, hit):
    word = WORDS[difficulty]
    start_game(page, difficulty)
    play_and_check(page, word, hit + MISSES, guess_by_key)

    expect(page.locator("#message")).to_have_class("loss")
    expect_revealed_loss(page, word, hit + MISSES)
    expect_parts(page, MAX_MISSES)
    expect_text(page, "#remaining", "Incorrect guesses left: 0 of 6")
    expect_enabled_keys(page, 0)
    watch.assert_clean()


def test_word_cells_and_label_follow_each_guess(page, watch):
    start_game(page, "medium")
    expect_word(page, "______")

    guess_by_key(page, "a")
    expect_word(page, "_A_A_A")
    guess_by_key(page, "n")
    expect_word(page, "_ANANA")
    guess_by_key(page, "z")
    expect_message(page, "No, Z is not in the word.")
    expect_word(page, "_ANANA")
    guess_by_key(page, "b")
    expect_word(page, "BANANA")
    watch.assert_clean()


def test_new_game_after_a_loss_resets_the_board_without_reloading(
    page, watch
):
    page.evaluate("window.marker = 1")
    start_game(page, "easy")
    play_and_check(page, WORDS["easy"], MISSES, guess_by_key)
    expect_parts(page, MAX_MISSES)

    start_game(page, "medium")

    assert page.evaluate("window.marker") == 1
    expect_parts(page, 0)
    expect_enabled_keys(page, 26)
    expect(page.locator("#keyboard .key.incorrect")).to_have_count(0)
    expect_word(page, "______")
    expect_text(page, "#remaining", remaining_text(0))
    expect_text(page, "#guessed-letters", "None yet")
    expect_text(page, "#incorrect-letters", "None yet")
    expect(page.locator("#message")).to_have_class("")
    assert watch.api_bodies()[-1]["difficulty"] == "medium"
    watch.assert_clean()


def test_changing_difficulty_keeps_the_game_in_progress(page, watch):
    start_game(page, "easy")
    guess_by_click(page, "z")
    expect_message(page, "No, Z is not in the word.")

    page.select_option("#difficulty", "medium")
    settle(page)

    expect(page.locator("#difficulty")).to_have_value("medium")
    assert watch.api_requests.count("POST /api/games") == 1
    expect_word(page, "_____")
    expect_parts(page, 1)
    guess_by_click(page, "a")
    expect_message(page, "Yes, A is in the word.")
    expect_word(page, "A____")
    watch.assert_clean()


def test_repeated_letter_on_the_keyboard_sends_no_request(page, watch):
    start_game(page, "easy")
    guess_by_key(page, "z")
    expect_message(page, "No, Z is not in the word.")
    sent = len(watch.api_requests)

    guess_by_key(page, "z")

    expect_message(page, "You already guessed Z.")
    settle(page)
    assert len(watch.api_requests) == sent
    expect_parts(page, 1)
    watch.assert_clean()


def test_typing_in_the_difficulty_select_sends_no_guess(page, watch):
    start_game(page, "medium")

    page.focus("#difficulty")
    page.keyboard.press("e")

    # The letter reached the select, which picked the matching option.
    expect(page.locator("#difficulty")).to_have_value("easy")
    settle(page)
    assert watch.guess_requests == []
    expect_message(page, STARTED)
    expect_enabled_keys(page, 26)
    watch.assert_clean()


def test_expired_game_shows_a_message_and_a_new_game_works(
    page, live, watch
):
    start_game(page, "easy")
    live.clock.advance(IDLE_TIMEOUT + 1)

    guess_by_click(page, "z")

    expect_message(page, EXPIRED)
    expect(page.locator("#message")).to_have_class("error")
    expect_enabled_keys(page, 0)
    expect_text(page, "#remaining", "No game in progress")
    expect(page.locator("#new-game")).to_be_focused()

    start_game(page, "medium")
    expect_enabled_keys(page, 26)
    guess_by_click(page, "b")
    expect_message(page, "Yes, B is in the word.")
    watch.assert_no_leaks()
    watch.assert_no_page_errors()


def test_unreachable_server_shows_a_message_and_play_resumes(page, watch):
    start_game(page, "easy")
    page.route("**/api/**", lambda route: route.abort())

    guess_by_click(page, "z")

    expect_message(page, UNREACHABLE)
    expect(page.locator("#message")).to_have_class("error")
    expect_enabled_keys(page, 26)
    expect_parts(page, 0)

    page.unroute("**/api/**")
    guess_by_click(page, "z")
    expect_message(page, "No, Z is not in the word.")
    expect_parts(page, 1)
    watch.assert_no_leaks()
    watch.assert_no_page_errors()


def test_keys_stay_enabled_while_a_guess_is_pending(page, live, watch):
    live.latency.seconds = SLOW_GUESS_SECONDS
    start_game(page, "easy")

    guess_by_key(page, "z")

    expect_enabled_keys(page, 26)
    expect_message(page, "No, Z is not in the word.")
    expect_enabled_keys(page, 25)
    watch.assert_clean()


def test_new_game_is_playable_while_an_old_guess_is_pending(
    page, live, watch
):
    live.latency.seconds = SLOW_GUESS_SECONDS
    start_game(page, "easy")
    guess_by_key(page, "a")

    start_game(page, "medium")

    expect_enabled_keys(page, 26)
    guess_by_click(page, "b")
    expect_message(page, "Yes, B is in the word.")
    expect_word(page, "B_____")
    watch.assert_clean()


def test_late_reply_from_an_old_game_leaves_the_new_board_alone(
    page, live, watch
):
    live.latency.seconds = SLOW_GUESS_SECONDS
    start_game(page, "easy")
    with page.expect_response(lambda reply: reply.url.endswith("/guess")):
        guess_by_key(page, "a")
        start_game(page, "medium")

    # The old reply has arrived. A guess now goes to the new game, unless
    # the old reply replaced it, in which case it goes to the wrong one.
    guess_by_click(page, "b")
    expect_message(page, "Yes, B is in the word.")
    expect_word(page, "B_____")
    expect_text(page, "#guessed-letters", "B")
    watch.assert_clean()


@pytest.mark.parametrize(
    ("focused", "earlier", "next_focused"),
    [
        pytest.param("c", "", "d", id="next-key"),
        pytest.param("c", "d", "e", id="skips-guessed-key"),
        pytest.param("z", "", "a", id="wraps-around"),
    ],
)
def test_focus_moves_to_the_next_enabled_key(
    page, watch, focused, earlier, next_focused
):
    start_game(page, "easy")
    type_letters(page, earlier)

    key_for(page, focused).focus()
    page.keyboard.press("Enter")

    expect(key_for(page, focused)).to_be_disabled()
    expect(key_for(page, next_focused)).to_be_focused()
    watch.assert_clean()


def test_long_word_fits_a_320px_phone(page, watch):
    page.set_viewport_size({"width": 320, "height": 700})
    word = WORDS["hard"]
    start_game(page, "hard")
    type_letters(page, distinct_letters(word))
    expect_message(page, won_message(word))

    cell_tops = page.eval_on_selector_all(
        "#word .cell",
        "cells => cells.map(c => Math.round(c.getBoundingClientRect().top))",
    )
    clipped_cells = page.eval_on_selector_all(
        "#word .cell",
        "cells => cells.filter(c => c.scrollWidth > c.clientWidth).length",
    )
    key_heights = page.eval_on_selector_all(
        "#keyboard .key",
        "keys => keys.map(k => k.getBoundingClientRect().height)",
    )
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - window.innerWidth"
    )

    assert len(cell_tops) == len(word)
    assert len(set(cell_tops)) == 1
    assert clipped_cells == 0
    assert overflow <= 0
    assert min(key_heights) >= 44
    watch.assert_clean()


def test_word_stays_hidden_until_the_game_ends(page, watch):
    word = WORDS["easy"]
    start_game(page, "easy")
    assert word not in page.content().lower()

    for letter in "zple":
        type_letters(page, letter)
        assert word not in page.content().lower()
    guess_by_key(page, "a")
    expect_message(page, won_message(word))

    revealing = [body for body in watch.api_bodies() if "word" in body]
    assert [body["status"] for body in revealing] == ["won"]
    assert revealing[0]["word"] == word
    watch.assert_clean()


def test_non_letter_keys_send_no_guess(page, watch):
    start_game(page, "easy")
    page.evaluate("document.activeElement.blur()")
    for key in ("1", "Minus", "Comma", "Slash", "F2", "ArrowLeft"):
        page.keyboard.press(key)
    settle(page)

    assert watch.guess_requests == []
    expect_message(page, STARTED)
    expect_enabled_keys(page, 26)
    watch.assert_clean()


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_shipped_app_plays_a_full_game_with_the_real_lists(
    browser, shipped_url, difficulty
):
    context = browser.new_context()
    watch = PageWatch(context.new_page())
    page = watch.page
    page.goto(shipped_url)
    start_game(page, difficulty)

    for letter in "etaoinsrhldcumfpgwybvkxjqz":
        type_letters(page, letter)
        final = watch.api_bodies()[-1]
        if final["status"] != "playing":
            break

    word = final["word"]
    assert word in WordManager.from_directory().words(difficulty)
    expect(page.locator("#message")).to_contain_text(word.upper())
    expect_enabled_keys(page, 0)
    watch.assert_clean()
    context.close()
