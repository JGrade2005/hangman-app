"""Flask REST API for the Hangman game."""

import os

from flask import Flask, Response, json, jsonify, request, url_for
from werkzeug.exceptions import BadRequest, HTTPException

from game import (
    DuplicateGuessError,
    GameOverError,
    InvalidGuessError,
    start_game,
)
from game_store import GameNotFoundError, GameStore
from word_manager import InvalidDifficultyError, WordManager

MAX_BODY_BYTES = 1024
BAD_BODY_MESSAGE = "Send a JSON object with Content-Type: application/json."
INTERNAL_ERROR_MESSAGE = "Internal server error."


def create_app(
    word_manager: WordManager | None = None,
    *,
    store: GameStore | None = None,
) -> Flask:
    """Build the Hangman API, loading the word lists by default."""
    if word_manager is None:
        word_manager = WordManager.from_directory()
    if store is None:
        store = GameStore()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    # Merged slashes answer with an HTML 308 redirect, which skips the JSON
    # error handlers, so a doubled slash is a plain 404 instead.
    app.url_map.merge_slashes = False
    _register_routes(app, word_manager, store)
    _register_error_handlers(app)
    _register_cache_headers(app)
    return app


def _json_object() -> dict[str, object]:
    """Return the request body, which must be a JSON object."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest(BAD_BODY_MESSAGE)
    return body


def _register_routes(
    app: Flask, words: WordManager, store: GameStore
) -> None:
    @app.post("/api/games")
    def create_game():
        difficulty = _json_object().get("difficulty")
        state = store.create(start_game(words, difficulty))
        location = url_for("get_game", game_id=state["game_id"])
        return jsonify(state), 201, {"Location": location}

    @app.get("/api/games/<game_id>")
    def get_game(game_id: str):
        return jsonify(store.state(game_id))

    @app.post("/api/games/<game_id>/guess")
    def guess_letter(game_id: str):
        letter = _json_object().get("letter")
        return jsonify(store.guess(game_id, letter))


def _error_response(message: str, status: int) -> tuple[Response, int]:
    return jsonify(error=message), status


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(InvalidDifficultyError)
    @app.errorhandler(InvalidGuessError)
    def handle_bad_request(error: Exception):
        return _error_response(str(error), 400)

    @app.errorhandler(GameNotFoundError)
    def handle_not_found(error: GameNotFoundError):
        return _error_response(str(error), 404)

    @app.errorhandler(DuplicateGuessError)
    @app.errorhandler(GameOverError)
    def handle_conflict(error: Exception):
        return _error_response(str(error), 409)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        # get_response keeps headers such as Allow on a 405.
        response = error.get_response()
        response.set_data(json.dumps({"error": error.description}))
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("Unhandled exception")
        return _error_response(INTERNAL_ERROR_MESSAGE, 500)


def _register_cache_headers(app: Flask) -> None:
    @app.after_request
    def disable_api_caching(response: Response) -> Response:
        if request.path == "/api" or request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


app = create_app()

if __name__ == "__main__":
    # Never enable debug here: the Werkzeug debugger runs arbitrary code.
    app.run(
        host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False
    )
