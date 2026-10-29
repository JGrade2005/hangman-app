import re

import pytest

from game_store import GameStore
from server import app as real_app
from server import create_app
from word_manager import DIFFICULTIES, WordManager

WORDS = {"easy": ["apple"], "medium": ["banana"], "hard": ["pineapple"]}
WORD_LENGTHS = {"easy": 5, "medium": 6, "hard": 9}
NOT_FOUND_MESSAGE = "Game not found. It may have expired, so start a new game."
BAD_BODY_MESSAGE = "Send a JSON object with Content-Type: application/json."
MISSES_FOR_APPLE = "zxqwvu"
SECRET = "boom: this must stay in the log"
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

BAD_BODIES = {
    "list body": {"json": ["easy"]},
    "string body": {"json": "easy"},
    "null body": {"data": "null", "content_type": "application/json"},
    "malformed json": {
        "data": '{"difficulty": ',
        "content_type": "application/json",
    },
    "no body": {},
    "wrong content type": {
        "data": '{"difficulty": "easy", "letter": "a"}',
        "content_type": "text/plain",
    },
}


class ExplodingStore(GameStore):
    """A store whose every operation fails unexpectedly."""

    def create(self, game):
        raise RuntimeError(SECRET)

    def state(self, game_id):
        raise RuntimeError(SECRET)

    def guess(self, game_id, letter):
        raise RuntimeError(SECRET)


class ExplodingWords(WordManager):
    """A word manager that fails when asked for a word."""

    def random_word(self, difficulty):
        raise RuntimeError(SECRET)


@pytest.fixture
def store() -> GameStore:
    return GameStore()


@pytest.fixture
def client(store):
    return create_app(WordManager(WORDS), store=store).test_client()


def create_game(client, difficulty="easy"):
    return client.post("/api/games", json={"difficulty": difficulty})


def new_game_id(client, difficulty="easy") -> str:
    return create_game(client, difficulty).get_json()["game_id"]


def get_state(client, game_id):
    return client.get(f"/api/games/{game_id}")


def guess(client, game_id, letter):
    return client.post(f"/api/games/{game_id}/guess", json={"letter": letter})


def play(client, game_id, letters):
    for letter in letters:
        response = guess(client, game_id, letter)
    return response


def assert_json_error(response, status):
    assert response.status_code == status
    assert response.content_type == "application/json"
    assert isinstance(response.get_json()["error"], str)


def assert_word_hidden(response):
    body = response.get_json()
    assert set(body) == PLAYING_KEYS
    assert body["status"] == "playing"
    assert "apple" not in response.get_data(as_text=True)


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_create_game(client, difficulty):
    response = create_game(client, difficulty)
    body = response.get_json()
    game_id = body.pop("game_id")

    assert response.status_code == 201
    assert response.content_type == "application/json"
    assert response.headers["Location"] == f"/api/games/{game_id}"
    assert re.fullmatch(r"[0-9a-f]{32}", game_id)
    assert body["pattern"].count("_") == WORD_LENGTHS[difficulty]
    assert body == {
        "difficulty": difficulty,
        "pattern": " ".join("_" * WORD_LENGTHS[difficulty]),
        "guessed_letters": [],
        "incorrect_letters": [],
        "remaining_guesses": 6,
        "max_incorrect_guesses": 6,
        "status": "playing",
    }


@pytest.mark.parametrize(
    ("sent", "difficulty"),
    [("EASY", "easy"), (" Medium ", "medium"), ("hArD", "hard")],
)
def test_create_game_normalizes_difficulty(client, sent, difficulty):
    response = create_game(client, sent)
    assert response.status_code == 201
    assert response.get_json()["difficulty"] == difficulty


def test_create_game_ignores_extra_keys(client):
    response = client.post(
        "/api/games", json={"difficulty": "easy", "word": "zebra"}
    )
    assert response.status_code == 201
    assert response.get_json()["pattern"] == "_ _ _ _ _"


def test_location_header_points_at_the_new_game(client):
    created = create_game(client)
    response = client.get(created.headers["Location"])
    assert response.status_code == 200
    assert response.get_json() == created.get_json()


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {"json": {}},
        {"json": {"difficulty": "expert"}},
        {"json": {"difficulty": None}},
        {"json": {"difficulty": 5}},
        *BAD_BODIES.values(),
    ],
    ids=[
        "missing difficulty",
        "unknown difficulty",
        "null difficulty",
        "numeric difficulty",
        *BAD_BODIES,
    ],
)
def test_create_game_rejects_bad_requests(client, store, request_kwargs):
    response = client.post("/api/games", **request_kwargs)
    assert_json_error(response, 400)
    assert len(store) == 0


def test_bad_difficulty_message_lists_the_choices(client):
    response = create_game(client, "expert")
    assert response.get_json() == {
        "error": "Difficulty must be one of: easy, medium, hard."
    }


def test_bad_body_message_explains_the_format(client):
    response = client.post("/api/games", json=["easy"])
    assert response.get_json() == {"error": BAD_BODY_MESSAGE}


def test_game_ids_are_unique(client):
    ids = {new_game_id(client) for _ in range(50)}
    assert len(ids) == 50


def test_games_are_independent(client):
    first = new_game_id(client)
    second = create_game(client).get_json()

    guess(client, first, "a")

    assert get_state(client, second["game_id"]).get_json() == second


def test_get_state_matches_the_last_guess(client):
    game_id = new_game_id(client)
    guess(client, game_id, "a")
    last = guess(client, game_id, "z")

    response = get_state(client, game_id)

    assert response.status_code == 200
    assert response.get_json() == last.get_json()


def test_get_unknown_game_is_not_found(client):
    response = get_state(client, "missing")
    assert_json_error(response, 404)
    assert response.get_json() == {"error": NOT_FOUND_MESSAGE}


def test_correct_guess_reveals_every_occurrence(client):
    game_id = new_game_id(client)

    response = guess(client, game_id, "p")

    assert response.status_code == 200
    body = response.get_json()
    assert body["pattern"] == "_ p p _ _"
    assert body["guessed_letters"] == ["p"]
    assert body["incorrect_letters"] == []
    assert body["remaining_guesses"] == 6
    assert body["status"] == "playing"


def test_incorrect_guess_costs_a_guess(client):
    game_id = new_game_id(client)

    body = guess(client, game_id, "z").get_json()

    assert body["pattern"] == "_ _ _ _ _"
    assert body["guessed_letters"] == ["z"]
    assert body["incorrect_letters"] == ["z"]
    assert body["remaining_guesses"] == 5


def test_uppercase_guess_is_accepted(client):
    game_id = new_game_id(client)

    response = guess(client, game_id, "P")

    assert response.status_code == 200
    assert response.get_json()["guessed_letters"] == ["p"]
    assert response.get_json()["pattern"] == "_ p p _ _"


@pytest.mark.parametrize(
    "body",
    [
        {"letter": ""},
        {"letter": "ab"},
        {"letter": "1"},
        {"letter": "é"},
        {"letter": None},
        {"letter": 5},
        {"letter": ["a"]},
        {},
    ],
    ids=[
        "empty",
        "two letters",
        "digit",
        "non-ascii",
        "null",
        "number",
        "list",
        "missing letter",
    ],
)
def test_invalid_letter_is_rejected(client, body):
    game_id = new_game_id(client)
    guess(client, game_id, "a")
    before = get_state(client, game_id).get_json()

    response = client.post(f"/api/games/{game_id}/guess", json=body)

    assert_json_error(response, 400)
    assert get_state(client, game_id).get_json() == before


@pytest.mark.parametrize(
    "request_kwargs", BAD_BODIES.values(), ids=BAD_BODIES.keys()
)
def test_guess_rejects_bad_bodies(client, request_kwargs):
    game_id = new_game_id(client)
    before = get_state(client, game_id).get_json()

    response = client.post(f"/api/games/{game_id}/guess", **request_kwargs)

    assert_json_error(response, 400)
    assert get_state(client, game_id).get_json() == before


@pytest.mark.parametrize("repeat", ["a", "A"])
def test_duplicate_guess_is_a_conflict(client, repeat):
    game_id = new_game_id(client)
    first = guess(client, game_id, "a")

    response = guess(client, game_id, repeat)

    assert_json_error(response, 409)
    assert response.get_json() == {"error": "You already guessed 'a'."}
    assert get_state(client, game_id).get_json() == first.get_json()


def test_guess_on_unknown_game_is_not_found(client):
    response = guess(client, "missing", "a")
    assert_json_error(response, 404)
    assert response.get_json() == {"error": NOT_FOUND_MESSAGE}


def test_winning_game_reveals_the_word(client):
    game_id = new_game_id(client)

    body = play(client, game_id, "aple").get_json()

    assert body["status"] == "won"
    assert body["word"] == "apple"
    assert body["pattern"] == "a p p l e"
    assert body["remaining_guesses"] == 6


def test_guess_after_a_win_is_a_conflict(client):
    game_id = new_game_id(client)
    play(client, game_id, "aple")

    response = guess(client, game_id, "z")

    assert_json_error(response, 409)
    state = get_state(client, game_id).get_json()
    assert state["status"] == "won"
    assert state["word"] == "apple"


def test_losing_game_reveals_the_word(client):
    game_id = new_game_id(client)

    body = play(client, game_id, MISSES_FOR_APPLE).get_json()

    assert body["status"] == "lost"
    assert body["remaining_guesses"] == 0
    assert body["incorrect_letters"] == list(MISSES_FOR_APPLE)
    assert body["word"] == "apple"


def test_guess_after_a_loss_is_a_conflict(client):
    game_id = new_game_id(client)
    play(client, game_id, MISSES_FOR_APPLE)

    response = guess(client, game_id, "a")

    assert_json_error(response, 409)
    state = get_state(client, game_id).get_json()
    assert state["status"] == "lost"
    assert state["word"] == "apple"


@pytest.mark.parametrize(
    "letters", ["aple", MISSES_FOR_APPLE], ids=["won", "lost"]
)
def test_new_game_after_a_finished_one(client, letters):
    old_id = new_game_id(client)
    finished = play(client, old_id, letters).get_json()

    response = create_game(client)
    fresh = response.get_json()

    assert response.status_code == 201
    assert fresh["game_id"] != old_id
    assert fresh["status"] == "playing"
    assert fresh["pattern"] == "_ _ _ _ _"
    assert fresh["remaining_guesses"] == 6
    assert fresh["guessed_letters"] == []
    assert "word" not in fresh
    assert get_state(client, old_id).get_json() == finished


@pytest.mark.parametrize(
    "letters", ["aple", MISSES_FOR_APPLE], ids=["win", "loss"]
)
def test_word_is_hidden_until_the_game_ends(client, letters):
    created = create_game(client)
    game_id = created.get_json()["game_id"]
    assert_word_hidden(created)

    for letter in letters[:-1]:
        assert_word_hidden(guess(client, game_id, letter))
        assert_word_hidden(get_state(client, game_id))

    final = guess(client, game_id, letters[-1])
    assert final.get_json()["word"] == "apple"


def test_unknown_route_is_a_json_404(client):
    assert_json_error(client.get("/api/nope"), 404)


def test_wrong_method_is_a_json_405(client):
    response = client.get("/api/games")
    assert_json_error(response, 405)
    assert "POST" in response.headers["Allow"]


def test_delete_game_is_a_json_405(client):
    game_id = new_game_id(client)
    response = client.delete(f"/api/games/{game_id}")
    assert_json_error(response, 405)
    assert get_state(client, game_id).status_code == 200


@pytest.mark.parametrize("path", ["/api/games", "/api/games/missing/guess"])
def test_oversized_body_is_a_json_413(client, path):
    padding = "x" * 2000
    response = client.post(
        path,
        data=f'{{"difficulty": "easy", "padding": "{padding}"}}',
        content_type="application/json",
    )
    assert_json_error(response, 413)


def test_api_responses_are_not_cacheable(client):
    game_id = new_game_id(client)
    oversized = client.post(
        "/api/games",
        data=" " * 2000,
        content_type="application/json",
    )
    responses = [
        create_game(client),
        get_state(client, game_id),
        guess(client, game_id, "a"),
        guess(client, game_id, "a"),
        guess(client, game_id, "1"),
        get_state(client, "missing"),
        client.get("/api/nope"),
        client.delete("/api/games"),
        oversized,
    ]
    for response in responses:
        assert response.headers["Cache-Control"] == "no-store"


def test_paths_outside_the_api_are_not_marked_no_store(client):
    response = client.get("/nope")
    assert_json_error(response, 404)
    assert "Cache-Control" not in response.headers


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/games"),
        ("get", "/api/games/abc"),
        ("post", "/api/games/abc/guess"),
    ],
)
def test_unexpected_error_is_a_json_500(method, path, caplog):
    app = create_app(WordManager(WORDS), store=ExplodingStore())
    request = getattr(app.test_client(), method)

    response = request(path, json={"difficulty": "easy", "letter": "a"})

    assert response.status_code == 500
    assert response.content_type == "application/json"
    assert response.get_json() == {"error": "Internal server error."}
    assert response.headers["Cache-Control"] == "no-store"
    assert SECRET not in response.get_data(as_text=True)
    assert "Traceback" not in response.get_data(as_text=True)
    assert SECRET in caplog.text


def test_word_manager_failure_is_a_json_500(caplog):
    app = create_app(ExplodingWords(WORDS))

    client = app.test_client()

    response = client.post("/api/games", json={"difficulty": "easy"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error."}
    assert SECRET in caplog.text


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_app_creates_games_from_the_word_lists(difficulty):
    response = real_app.test_client().post(
        "/api/games", json={"difficulty": difficulty}
    )
    body = response.get_json()

    assert response.status_code == 201
    assert set(body["pattern"].replace(" ", "")) == {"_"}
    assert body["remaining_guesses"] == 6
    assert body["status"] == "playing"
    assert "word" not in body


def test_doubled_slashes_are_a_json_404_not_a_redirect(client):
    game_id = new_game_id(client)
    assert_json_error(client.get("/api/games//guess"), 404)
    response = client.post(
        f"/api/games//{game_id}/guess", json={"letter": "a"}
    )
    assert_json_error(response, 404)


def test_api_root_is_not_cacheable(client):
    response = client.get("/api")
    assert_json_error(response, 404)
    assert response.headers["Cache-Control"] == "no-store"
