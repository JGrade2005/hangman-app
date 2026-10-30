# Hangman Web App

A Hangman game you can play in the browser. A pure-Python game engine runs behind a Flask REST API, and a plain HTML, CSS and JavaScript page talks to that API with `fetch()`. The server is in charge of every game: the browser never sees the hidden word until the game is over.

**Live site:** https://hangman-app-mom6.onrender.com/

It runs on Render's free tier. If nobody has visited for 15 minutes the server sleeps, and the first visit then takes about a minute while it wakes up. The page says so, then plays normally.

## Features

- Easy, Medium and Hard word lists (188, 211 and 234 words).
- Guess by clicking the on-screen keyboard or by typing on your own keyboard.
- The page shows:
  - the word pattern;
  - the letters guessed and the incorrect letters;
  - the incorrect guesses remaining (6 per game);
  - a hangman drawing that adds one part per miss;
  - a win or loss message that reveals the word.
- Start a new game at any time without reloading the page.
- Works from 320px-wide phones to desktop, in light and dark themes, with full keyboard support and screen-reader labels.

## Run it locally

You need Python 3.12 (the version used for development and pinned for deployment) and Git.

```bash
git clone https://github.com/JGrade2005/hangman-app.git
cd hangman-app
python3.12 -m venv .venv           # Windows: py -3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:5000 in a browser. Press Ctrl+C in the terminal to stop the server.

`python server.py` runs Flask's development server with debug mode off. To run it the way production does:

```bash
gunicorn server:app
```

This reads [gunicorn.conf.py](gunicorn.conf.py) and serves http://127.0.0.1:8000. If the `PORT` environment variable is set, as it is on Render, it listens on all interfaces at that port instead. Gunicorn runs on Linux and macOS only, so on Windows use `python server.py`.

## How to play

1. Pick a difficulty and press **New game**. Changing the difficulty later applies to the next game, not the one in progress.
2. Guess a letter by clicking it or typing it. Correct letters fill in the word; each miss adds a part to the drawing.
3. You win by revealing the whole word before the sixth miss. After a win or a loss the word is shown and **New game** has focus, so Enter starts another round.

If the page says the game has expired, the server restarted (free hosting does this when idle). Press New game to carry on.

## Project structure

```text
game.py             Game engine: HangmanGame, guess rules, win/loss, client-safe state
word_manager.py     Loads, cleans and picks words from words/*.txt by difficulty
game_store.py       Thread-safe in-memory games by ID, with idle expiry and a cap
server.py           Flask app: REST API, JSON errors, security headers, serves the page
static/             Browser client: index.html, style.css, app.js, favicon.svg
words/              easy.txt, medium.txt, hard.txt (one lowercase word per line)
tests/              pytest suites for each layer, plus Playwright browser tests
pytest.ini          Test paths and the "ui" marker for the browser tests
progress.py         Writes PROGRESS.md from the TODO.md checkboxes
gunicorn.conf.py    Production server settings (1 worker, 4 threads, PORT binding)
render.yaml         Render Blueprint for deployment
.python-version     Pins Python 3.12 on Render
requirements.txt    Runtime dependencies (Flask, gunicorn)
requirements-dev.txt  Test dependencies (pytest, Playwright)
Specification.md    The original project specification
TODO.md             Implementation checklist, by phase
PROGRESS.md         Progress bars generated from TODO.md by progress.py
DEV_LOG.md          Development log: prompts, decisions, problems and fixes
```

## How it works

```text
Browser (static/app.js)  --fetch, JSON-->  Flask (server.py)  -->  GameStore  -->  HangmanGame
holds: game_id + last reply                 routes + errors          id -> game      word + guesses
```

- **The engine** ([game.py](game.py)) stores only the hidden word and the letters guessed. The pattern, incorrect letters, remaining guesses and status (`playing`, `won`, `lost`) are recalculated from those two on every request, so they can never disagree. It has no Flask or browser code and is tested on its own.
- **The store** ([game_store.py](game_store.py)) keeps games in memory, keyed by a random `uuid4` ID. One lock covers each whole operation, so two requests at the same moment cannot both pass the duplicate-guess check.
- **The game ID travels in the URL** (`/api/games/<game_id>/guess`). The request body carries only the action's data (`{"letter": "e"}`). There are no cookies or sessions, so the API works the same from a browser, curl or a bot.
- **The browser** keeps one variable: the last JSON reply from the server, which includes `game_id` and `status`. It builds each request URL from that ID and redraws the page from each reply. It never works out a game result itself, and it never sends a status, a pattern or a word to the server.
- **The word stays on the server.** `to_state()` adds `word` to a response only once the game has ended. The tests check this at the engine, API and browser levels.

## REST API

All requests and responses are JSON. Send `Content-Type: application/json` on POST requests.

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/api/games` | `{"difficulty": "easy" \| "medium" \| "hard"}` (any case) | `201` with the game state and a `Location` header |
| GET | `/api/games/{game_id}` | none | `200` with the game state |
| POST | `/api/games/{game_id}/guess` | `{"letter": "e"}` (one letter A to Z, any case) | `200` with the updated game state |

### Game state

| Field | Meaning |
|---|---|
| `game_id` | 32-character hex ID for this game |
| `difficulty` | `easy`, `medium` or `hard` |
| `pattern` | The word with unguessed letters as `_`, separated by spaces, e.g. `"_ p p _ _"` |
| `guessed_letters` | Every accepted guess, in order |
| `incorrect_letters` | The misses, in order |
| `remaining_guesses` | Incorrect guesses left (starts at 6) |
| `max_incorrect_guesses` | Always 6 |
| `status` | `playing`, `won` or `lost` |
| `word` | The answer. **Only present once `status` is `won` or `lost`.** |

### Errors

Every error is JSON in the form `{"error": "<message>"}`. The message is safe to show to a player.

| Status | When |
|---|---|
| 400 | The body is not a JSON object, the difficulty is not easy, medium or hard, or the letter is not a single letter A to Z |
| 404 | Unknown or expired game ID, or unknown route |
| 405 | Wrong HTTP method for the route |
| 409 | The letter was already guessed, or the game is already over |
| 413 | The request body is over 1 KB |
| 500 | Unexpected server error (no details are exposed) |

API responses carry `Cache-Control: no-store`. Every response carries a Content-Security-Policy (`default-src 'self'`) and `X-Content-Type-Options: nosniff`.

### Example session

These are real responses. The server was started with the Easy list fixed to "apple" so the example is predictable.

```bash
curl -X POST http://127.0.0.1:5000/api/games \
     -H "Content-Type: application/json" -d '{"difficulty": "easy"}'
```

```json
{"difficulty":"easy","game_id":"40008ecf8eb948a0821f7bfdf3dd10ff","guessed_letters":[],"incorrect_letters":[],"max_incorrect_guesses":6,"pattern":"_ _ _ _ _","remaining_guesses":6,"status":"playing"}
```

```bash
curl -X POST http://127.0.0.1:5000/api/games/40008ecf8eb948a0821f7bfdf3dd10ff/guess \
     -H "Content-Type: application/json" -d '{"letter": "p"}'
```

```json
{"difficulty":"easy","game_id":"40008ecf8eb948a0821f7bfdf3dd10ff","guessed_letters":["p"],"incorrect_letters":[],"max_incorrect_guesses":6,"pattern":"_ p p _ _","remaining_guesses":6,"status":"playing"}
```

A miss (`"z"`), then `GET /api/games/40008ecf8eb948a0821f7bfdf3dd10ff`:

```json
{"difficulty":"easy","game_id":"40008ecf8eb948a0821f7bfdf3dd10ff","guessed_letters":["p","z"],"incorrect_letters":["z"],"max_incorrect_guesses":6,"pattern":"_ p p _ _","remaining_guesses":5,"status":"playing"}
```

After guessing `a`, `l` and `e`, the game is won and the word appears for the first time:

```json
{"difficulty":"easy","game_id":"40008ecf8eb948a0821f7bfdf3dd10ff","guessed_letters":["p","z","a","l","e"],"incorrect_letters":["z"],"max_incorrect_guesses":6,"pattern":"a p p l e","remaining_guesses":5,"status":"won","word":"apple"}
```

Errors from the same session:

```text
409  {"error":"You already guessed 'p'."}
400  {"error":"Guess a single letter from A to Z."}
409  {"error":"This game is over. Start a new game."}
400  {"error":"Difficulty must be one of: easy, medium, hard."}
404  {"error":"Game not found. It may have expired, so start a new game."}
400  {"error": "Send a JSON object with Content-Type: application/json."}
```

## Testing

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium      # once, for the browser tests
python -m pytest
```

On a fresh Linux machine, Chromium may also need system libraries. `python -m playwright install --with-deps chromium` installs them (it asks for sudo).

292 tests run in about 20 seconds. To skip the browser tests (for example without Chromium), run `python -m pytest -m "not ui"`. Without Chromium installed, the browser tests skip themselves with a message saying how to install it.

| File | Tests | Covers |
|---|---|---|
| [tests/test_game.py](tests/test_game.py) | 72 | Engine: correct, incorrect, duplicate and invalid guesses; win; loss; guesses after the end; the word hidden until the end |
| [tests/test_word_manager.py](tests/test_word_manager.py) | 62 | Word loading and cleaning, random choice for all three difficulties, invalid difficulties |
| [tests/test_game_store.py](tests/test_game_store.py) | 23 | Unique IDs, expiry and eviction with a fake clock, a lock test proven to fail without the lock |
| [tests/test_api.py](tests/test_api.py) | 68 | Every route and status code, invalid requests, a new game after a finished one, exact response fields while playing |
| [tests/test_web.py](tests/test_web.py) | 42 | Page and assets served, security headers, no inline code, no word list shipped to the browser |
| [tests/test_ui.py](tests/test_ui.py) | 25 | Playwright in headless Chromium: a win and a loss at every difficulty, with the whole UI checked after every guess; new game without reload; expired game; unreachable server; slow-network races; keyboard focus; 320px phone layout; full games on the real word lists |

Every browser test fails if any API response during play contains the word, or if the page logs an error. The browser tests start their own server on a free port, so nothing needs to be running first.

## Deployment (Render)

The app is deployed from this repository with the [render.yaml](render.yaml) Blueprint:

1. Push the repository to GitHub.
2. In the Render dashboard choose **New**, then **Blueprint**, and select the repository.
3. Render creates a free Python web service that runs `pip install -r requirements.txt` and then `gunicorn server:app`, with a health check on `/`.

Every push to `main` redeploys automatically.

Deployment notes:

- **One worker, four threads.** Games live in the server process's memory, and each Gunicorn worker is a separate process with its own memory. In a local test with 2 workers, 8 of 100 lookups for existing games returned 404; with 1 worker, none did. Threads share memory, and the store's lock keeps them safe. These settings live in [gunicorn.conf.py](gunicorn.conf.py), which also binds to `0.0.0.0` on Render's `PORT`.
- **Python 3.12** is pinned by [.python-version](.python-version), because Render otherwise uses its newest default.
- **Free-tier behavior.** Render may restart the service, and it spins down after 15 idle minutes. Either way, all in-memory games are cleared. A player in the middle of a game then sees "This game has expired" and can start a new one. The page waits up to 90 seconds for a reply, which covers the roughly one-minute wake-up.

## Differences from the specification

[Specification.md](Specification.md) describes a larger platform. This assignment covers the game engine, the REST API, the browser client, tests and deployment, so these parts of the spec are **not built**: the terminal client, the example bots, evaluation mode, scoring, the leaderboard, and logging and replay. [TODO.md](TODO.md) lists every original item, with the out-of-scope ones in their own section.

Within the parts that are built:

- **Extra response fields.** Responses include `game_id`, `difficulty` and `max_incorrect_guesses` on every call, and the spec's create and guess examples are subsets of the state above.
- **Duplicate guesses are rejected with 409.** The spec allows them to be ignored or rejected. Either way, a rejected guess never changes the game.
- **Patterns are lowercase,** as in the spec's examples. The browser displays them in uppercase.
- **Difficulty names are accepted in any case and with surrounding spaces.**
- **A missing or wrong `Content-Type` gets 400.** 415 would be the more specific code, but the assignment lists 400 for invalid requests.
- **Games are kept in memory only.** They expire after 1 hour without use, at most 10,000 are kept (the least recently used is dropped first), and a server restart clears them all.

## Known limitations

- A page reload forgets the current game (the browser keeps the game ID only in memory). Start a new game after reloading.
- Anyone who has a game's ID can play that game. IDs are `uuid4` values with 122 random bits, so they cannot realistically be guessed, but there are no accounts.
- A letter typed while the previous guess is still waiting for the server is ignored, which keeps one request per game in flight.
- The class word lists contain the words "easy" (Easy list) and "medium" (Medium list). In those games the word's text also appears as the `difficulty` value. This reveals nothing, because the difficulty is the player's own choice and is the same for every game at that level, and a test confirms the state matches that of any other word of the same length.

## Development

Built for CSE4095 (Class 14) with Claude Code. Opus led design and review, Sonnet subagents wrote most of the code, and Haiku subagents checked work against the spec and TODO. [DEV_LOG.md](DEV_LOG.md) records the prompts, decisions, problems and fixes for each phase. Run `python progress.py` to refresh [PROGRESS.md](PROGRESS.md) from [TODO.md](TODO.md).
