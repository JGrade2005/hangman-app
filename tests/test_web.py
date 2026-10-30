"""Tests for the static browser client and the headers that protect it.

Browser behavior is covered by the Playwright test in tests/test_ui.py.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from server import create_app
from word_manager import DIFFICULTIES, WordManager

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "static"
WORDS_DIR = ROOT / "words"
WORDS = {"easy": ["apple"], "medium": ["banana"], "hard": ["pineapple"]}
CSP = (
    "default-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)
REQUIRED_IDS = [
    "difficulty",
    "new-game",
    "message",
    "drawing",
    "word",
    "remaining",
    "guessed-letters",
    "incorrect-letters",
    "keyboard",
]
STATIC_TYPES = [
    ("/static/app.js", {"text/javascript", "application/javascript"}),
    ("/static/style.css", {"text/css"}),
    ("/static/favicon.svg", {"image/svg+xml"}),
]
PAGE_AND_ASSETS = [
    "/",
    "/static/app.js",
    "/static/style.css",
    "/static/favicon.svg",
]
REQUESTS = [
    ("GET", "/"),
    ("GET", "/static/app.js"),
    ("GET", "/static/style.css"),
    ("GET", "/static/favicon.svg"),
    ("POST", "/api/games"),
    ("GET", "/api/games/unknown"),
    ("GET", "/missing"),
]
INLINE_CODE_PATTERNS = {
    "inline script": r"<script\b(?![^>]*\bsrc=)",
    "style block": r"<style\b",
    "style attribute": r"<[^>]*\sstyle\s*=",
    "event handler attribute": r"<[^>]*\son[a-z]+\s*=",
    "javascript url": r"javascript:",
}
# Ordinary words that the page code needs (JavaScript keywords, element ids,
# option values) and that also happen to be in the word lists.
UI_WORDS = {
    "change",
    "function",
    "letter",
    "medium",
    "message",
    "number",
    "remove",
    "request",
    "return",
}
MIN_LEAKABLE_LENGTH = 6
BANNED_JS_PATTERNS = {
    "var declaration": r"\bvar\b",
    "innerHTML": r"innerHTML",
    "console call": r"\bconsole\.",
}


class PartCollector(HTMLParser):
    """Collects every element that has a data-part attribute."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if "data-part" in attributes:
            self.parts.append((tag, attributes))


@pytest.fixture
def client() -> FlaskClient:
    return create_app(WordManager(WORDS)).test_client()


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def send(client: FlaskClient, method: str, path: str) -> TestResponse:
    body = {"difficulty": "easy"} if method == "POST" else None
    return client.open(path, method=method, json=body, buffered=True)


def word_tokens(text: str) -> set[str]:
    """Return the lowercase words in text, splitting camelCase names."""
    names = re.findall(r"[A-Za-z]+", text)
    pieces = (re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", n) for n in names)
    return {piece.lower() for group in pieces for piece in group}


def list_words() -> set[str]:
    words = (
        line.strip().lower()
        for path in WORDS_DIR.glob("*.txt")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    return {word for word in words if len(word) >= MIN_LEAKABLE_LENGTH}


def test_index_page_is_html(client):
    response = send(client, "GET", "/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<h1>Hangman</h1>" in response.get_data(as_text=True)


@pytest.mark.parametrize("element_id", REQUIRED_IDS)
def test_index_has_required_ids(client, element_id):
    html = send(client, "GET", "/").get_data(as_text=True)

    assert f'id="{element_id}"' in html


def test_index_references_its_assets(client):
    html = send(client, "GET", "/").get_data(as_text=True)

    assert re.search(r'<script[^>]*type="module"', html)
    assert 'src="/static/app.js"' in html
    assert 'href="/static/style.css"' in html
    assert 'href="/static/favicon.svg"' in html


@pytest.mark.parametrize(("path", "mimetypes"), STATIC_TYPES)
def test_static_files_have_sensible_content_types(client, path, mimetypes):
    response = send(client, "GET", path)

    assert response.status_code == 200
    assert response.mimetype in mimetypes
    assert response.get_data()


@pytest.mark.parametrize(("method", "path"), REQUESTS)
def test_every_response_has_security_headers(client, method, path):
    response = send(client, method, path)

    assert response.headers["Content-Security-Policy"] == CSP
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("path", PAGE_AND_ASSETS)
def test_page_and_assets_are_not_marked_no_store(client, path):
    response = send(client, "GET", path)

    assert "no-store" not in response.headers.get("Cache-Control", "")


@pytest.mark.parametrize(
    "pattern", INLINE_CODE_PATTERNS.values(), ids=list(INLINE_CODE_PATTERNS)
)
def test_index_has_no_inline_code(pattern):
    assert not re.search(pattern, read_static("index.html"), re.IGNORECASE)


def test_index_script_tags_have_a_source_and_no_body():
    html = read_static("index.html")
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.DOTALL)

    assert scripts
    for attributes, body in scripts:
        assert 'src="' in attributes
        assert not body.strip()


def test_drawing_has_six_numbered_body_parts():
    html = read_static("index.html")
    svg = re.search(r'<svg id="drawing".*?</svg>', html, re.DOTALL)
    assert svg
    collector = PartCollector()
    collector.feed(svg.group(0))

    numbers = [attrs["data-part"] for _, attrs in collector.parts]
    assert numbers == ["1", "2", "3", "4", "5", "6"]
    assert collector.parts[0][0] == "circle"
    assert all(
        "part" in attrs["class"].split() for _, attrs in collector.parts
    )


def test_app_js_uses_fetch_and_the_api_paths():
    js = read_static("app.js")

    assert "fetch(" in js
    assert '"/api/games"' in js
    assert "/guess" in js
    assert '"Content-Type": "application/json"' in js


def test_no_list_words_of_six_or_more_letters_ship_to_the_browser():
    shipped = word_tokens(read_static("app.js") + read_static("index.html"))

    assert (shipped & list_words()) <= UI_WORDS


@pytest.mark.parametrize(
    "pattern", BANNED_JS_PATTERNS.values(), ids=list(BANNED_JS_PATTERNS)
)
def test_app_js_avoids_banned_constructs(pattern):
    assert not re.search(pattern, read_static("app.js"))


@pytest.mark.parametrize(
    "name", ["index.html", "app.js", "style.css", "favicon.svg"]
)
def test_static_files_have_no_em_dashes(name):
    assert "\u2014" not in read_static(name)


def test_difficulty_options_match_the_server():
    options = re.findall(
        r'<option value="([a-z]+)"', read_static("index.html")
    )
    assert tuple(options) == DIFFICULTIES
