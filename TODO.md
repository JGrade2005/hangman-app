# TODO: Hangman Web App

This file is the implementation roadmap for the Hangman web app.

The authoritative system requirements are defined in `Specification.md`, which is kept as the original. Where this checklist and the spec or the assignment brief differ, the spec and the brief win.

Reorganized on 2026-10-29. The original file arrived with every box already checked from a different project, so every box was reset. Each original item now sits under the phase that does it, tagged with its original phase, e.g. `(P1)`. Items tagged `(brief)` come from the assignment brief, and `(plan)` items come from the approved Phase 1 plan. Original items outside this assignment's scope are kept, unchanged, in the "Out of Scope" section at the end.

Run `python progress.py` to refresh `PROGRESS.md`.

## Implementation Rules

- Implement one phase at a time.
- Complete and test all items in the current phase before moving to the next phase.
- Do not change the architecture or REST API defined in `Specification.md` unless necessary.
- If a deviation is necessary, document it in the README. The spec stays as the original for submission (changed from "update the specification").
- Keep the game engine independent from Flask and the browser UI.
- The server must remain authoritative.
- Never expose the hidden word before a game ends.
- Add tests as each phase is implemented rather than postponing testing until the end.

---

## Phase 1: Review and Plan

### Tasks

- [x] Read `~/agenticlibrary`, `Specification.md`, `TODO.md`, and the Cursor transcript. (brief)
- [x] Map every spec requirement and TODO item to a phase. (brief)
- [x] Get the plan approved before writing code. (brief)

### Completion Criteria

The plan is approved, and every spec requirement and TODO item has a phase or is marked out of scope.

---

## Phase 2: Initialize the Project

### Tasks

- [x] Create the project directory structure. (P1)
- [x] Add `words/easy.txt`. (P1)
- [x] Add `words/medium.txt`. (P1)
- [x] Add `words/hard.txt`. (P1)
- [x] Create a Python 3.12 virtual environment in `.venv/`. (brief)
- [x] Add dependency information such as `requirements.txt` or `pyproject.toml`. (P14)
- [x] Add `requirements-dev.txt` for test-only dependencies. (plan)
- [x] Add `.gitignore`. (brief)
- [x] Run `git init`. The user does all commits and pushes. (brief)
- [x] Ignore this folder in the parent `CSE4095_2026` repo so the two repos do not nest. (plan)
- [x] Reorganize `TODO.md` around the assignment phases. (plan)
- [x] Add `progress.py`, which writes `PROGRESS.md` from this checklist. (plan)

### Completion Criteria

The virtual environment imports Flask and pytest, the three word lists are in place and clean, and `git status` in the new repo lists only intended files.

---

## Phase 3: Game Engine (A)

### Tasks

Word management:

- [x] Create a word-loading module or helper functions. (P2)
- [x] Load Easy, Medium, and Hard word lists. (P2)
- [x] Validate that loaded words contain only alphabetic characters. (P2)
- [x] Remove accidental duplicates when loading. (P2)
- [x] Support random word selection by difficulty. (P2)
- [x] Return an error for an invalid difficulty. (P2)
- [x] Add tests for word loading and word selection. (P2)

Game:

- [x] Create `game.py`. (P1)
- [x] Implement a `HangmanGame` class. (P1)
- [x] Store the hidden word internally. (P1)
- [x] Track guessed letters. (P1)
- [x] Track incorrect letters. (P1)
- [x] Track the maximum number of incorrect guesses. (P1)
- [x] Track correct guesses and remaining incorrect guesses. (brief)
- [x] Implement single-letter guess validation. (P1)
- [x] Detect duplicate guesses. (P1)
- [x] Implement masked-word generation. (P1)
- [x] Implement win detection. (P1)
- [x] Implement loss detection. (P1)
- [x] Implement game status values such as `playing`, `won`, and `lost`. (P1)
- [x] Refuse further guesses once a game is over. (brief)
- [x] Implement a method that returns a client-safe game-state dictionary. (P1)
- [x] Reveal the answer only after the game ends. (P1)
- [x] Add unit tests for the game engine. (P1)

Tests:

- [x] Complete unit tests for `HangmanGame`. (P13)
- [x] Complete tests for word loading. (P13)
- [x] Test all three difficulties. (brief)
- [x] Test duplicate guesses. (P13)
- [x] Test invalid letters. (P13)
- [x] Test invalid difficulty. (P13)
- [x] Test win paths. (P13)
- [x] Test loss paths. (P13)

### Completion Criteria

The game engine can be tested entirely without running a web server. (P1)

All core rules are covered by unit tests. (P1)

The program can request a random word from each difficulty level reliably. (P2)

Invalid difficulty values are rejected cleanly. (P2)

---

## Phase 4: Flask Server and REST API (B)

### Tasks

- [ ] Create `server.py`. (P3)
- [ ] Configure Flask or FastAPI. (P3)
- [ ] Add in-memory storage for active games. (P3)
- [ ] Keep each game's state separate and safe under concurrent requests. (brief)
- [ ] Remove idle games so memory stays bounded. (plan)
- [ ] Generate unique game IDs. (P3)
- [ ] Implement `POST /api/games`. (P3)
- [ ] Implement `GET /api/games/{game_id}`. (P3)
- [ ] Implement `POST /api/games/{game_id}/guess`. (P3)
- [ ] Validate difficulty input. (P3)
- [ ] Validate guess input. (P3)
- [ ] Return JSON responses consistently. (P3)
- [ ] Return appropriate HTTP status codes. (P3)
- [ ] Handle unknown game IDs. (P3)
- [ ] Handle malformed requests. (P3)
- [ ] Ensure the hidden word is never leaked during an active game. (P3)
- [ ] Ensure game state responses never contain the answer while status is `playing`. (P11)
- [ ] Add API tests. (P3)

Tests:

- [ ] Complete REST API tests. (P13)
- [ ] Test missing game IDs. (P13)
- [ ] Test answer disclosure rules. (P13)
- [ ] Test invalid API requests (bad JSON, wrong types, bad difficulty, bad letter). (brief)
- [ ] Test a new game after a finished one. (brief)

### Completion Criteria

A complete Hangman game can be played using only `curl` or another HTTP client. (P3)

The browser client is not required for this phase. (P3, adapted: the terminal client is out of scope)

---

## Phase 5: Web Client (C)

### Tasks

- [ ] Create `static/index.html`. (P5)
- [ ] Create `static/style.css`. (P5)
- [ ] Create `static/app.js`. (P5)
- [ ] Serve the web client from Flask. (brief)
- [ ] Add a difficulty selector. (P5)
- [ ] Add a New Game button. (P5)
- [ ] Display the masked word. (P5)
- [ ] Display guessed letters. (P5)
- [ ] Display incorrect letters. (P5)
- [ ] Display remaining guesses. (P5)
- [ ] Add an on-screen alphabet keyboard. (P5)
- [ ] Accept guesses from the physical keyboard. (brief)
- [ ] Disable already-guessed letters. (P5)
- [ ] Use `fetch()` to communicate with the REST API. (P5)
- [ ] Draw the Hangman state visually. (P5)
- [ ] Update the drawing after incorrect guesses. (P5)
- [ ] Display win and loss messages. (P5)
- [ ] Provide a restart/new-game flow. (P5)
- [ ] Start a new game without reloading the page. (brief)
- [ ] Show server and network errors, including an expired game. (plan)
- [ ] Make the interface usable on common desktop and mobile browser sizes. (P5)

### Completion Criteria

A human player can play the same server-hosted game from a browser. (P5)

No hidden word is stored in browser-side JavaScript. (P5)

---

## Phase 6: Local Testing (D)

### Tasks

- [ ] Test browser-client integration. (P13)
- [ ] Add an end-to-end automated test. (P13)
- [ ] Run the full pytest suite with every test passing. (brief)
- [ ] Play a browser game at each difficulty, covering a win and a loss. (brief)
- [ ] Confirm in the network log that no response contains the word while a game is playing. (plan)
- [ ] Run the app locally under Gunicorn with the production start command. (plan)

### Completion Criteria

The major user flows and failure cases are covered by automated tests. (P13)

---

## Phase 7: Deployment (E)

### Tasks

- [ ] Add `render.yaml` with the Gunicorn start command (1 worker, 4 threads). (brief)
- [ ] Pin the Python version. (plan)
- [ ] Recheck Render free-tier behavior (sleep, wake time, monthly hours). (plan)
- [ ] User: create the GitHub repo, commit, and push. (brief)
- [ ] User: sign in to Render and apply the Blueprint. (brief)
- [ ] Verify the live HTTPS URL with HTTP requests (create, guess, win, loss, errors, no word leak). (brief)
- [ ] Play a complete game on the live URL in a browser. (brief)

### Completion Criteria

A user can play a complete game at a public HTTPS URL with nothing installed. (brief)

---

## Phase 8: Submission Package

### Tasks

- [ ] Create or update `README.md`. (P14)
- [ ] Document installation. (P14)
- [ ] Document how to start the server. (P14)
- [ ] Document how to use the browser client. (P14)
- [ ] Document the REST API. (P14)
- [ ] Provide example requests and responses. (P14)
- [ ] Document testing and deployment. (brief)
- [ ] Document deviations from the spec and out-of-scope items. (plan)
- [ ] Verify that a fresh installation works from the documented instructions. (P14)
- [ ] Finalize `TODO.md` and `DEV_LOG.md`. (brief)
- [ ] Draft `REPORT_NOTES.md`, leaving the reflection section for the user. (brief)
- [ ] Write the session log in `~/agenticlibrary`. (plan)

### Completion Criteria

A new user can clone the project, install dependencies, start the server, and play from the browser using only the documentation. (P14, adapted: the terminal client and bots are out of scope)

---

## Recommended Development Order

Phases 1 to 8 above, in order. This replaces the original 14-step order, which followed the original phase numbers.

The project should remain runnable after every completed phase.

---

# Out of Scope

These original items are not part of this assignment's brief (parts A to E), so they are not built. They are kept unchanged for reference, as plain bullets so they are not counted as open tasks.

## Original Phase 4: Human Terminal Client

- Create `terminal_client.py`.
- Connect to the Hangman server over HTTP.
- Let the user choose Easy, Medium, or Hard.
- Start a new game through the REST API.
- Display the masked word.
- Display guessed letters.
- Display incorrect letters.
- Display remaining incorrect guesses.
- Prompt for one letter at a time.
- Submit guesses through the REST API.
- Handle invalid input locally when appropriate.
- Handle server errors gracefully.
- Display win and loss messages.
- Allow the user to start another game.

## Original Phase 6: Reference Automated Clients

- Create `bot_examples/`.
- Implement `random_bot.py`.
- Implement `frequency_bot.py`.
- Define a common bot interaction pattern.
- Create a reusable HTTP client helper if useful.
- Make each bot capable of playing a complete game automatically.
- Print game results and summary statistics.
- Ensure bots use only information exposed through the REST API.
- Document how students can write their own bot.

## Original Phase 7: Dictionary-Based Bot Example

- Implement `dictionary_bot.py`.
- Load an allowed training dictionary.
- Filter candidate words by current pattern.
- Remove candidates containing known incorrect letters.
- Respect known letter positions.
- Track letters already guessed.
- Compute candidate-letter frequencies.
- Choose the next letter using the remaining candidates.
- Fall back to global letter frequency if no candidates remain.
- Compare its performance against the random and frequency bots.

## Original Phase 8: Evaluation Mode

- Separate normal game play from official evaluation mode.
- Add an evaluation-session model.
- Generate a unique evaluation ID.
- Define the number of evaluation games.
- Support evaluation across Easy, Medium, and Hard words.
- Ensure the server controls all evaluation words.
- Prevent skipping or restarting unfavorable evaluation games.
- Require games to be played in the intended sequence.
- Record wins and losses.
- Record total guesses.
- Record incorrect guesses.
- Record remaining guesses after wins.
- Record per-game results.
- Add evaluation API endpoints.
- Add tests for evaluation integrity.

## Original Phase 9: Scoring System

- Define the official scoring formula.
- Make wins the primary performance signal.
- Use guess efficiency as a secondary signal or tiebreaker.
- Define how losses are scored.
- Define how invalid guesses affect scoring.
- Define how duplicate guesses affect scoring.
- Define how abandoned games affect scoring.
- Record total score for each evaluation.
- Add tests for scoring calculations.
- Document the scoring rules clearly for students.

## Original Phase 10: Leaderboard

- Define a leaderboard record format.
- Store participant or bot name.
- Store total games.
- Store games won.
- Store win rate.
- Store average guesses.
- Store average remaining guesses on wins.
- Store total score.
- Rank results consistently.
- Add a leaderboard API endpoint.
- Add a browser leaderboard view.
- Display rankings in the terminal if useful.
- Decide whether leaderboard data should persist across server restarts.

## Original Phase 11: Evaluation Integrity and Anti-Cheating Safeguards

The first item of this phase, "Ensure game state responses never contain the answer while status is `playing`", moved to Phase 4.

- Ensure evaluation words are server-controlled.
- Prevent clients from requesting arbitrary evaluation game IDs.
- Reject malformed or unauthorized evaluation requests.
- Add optional rate limiting if needed.
- Add optional per-request timeout rules.
- Log evaluation actions.
- Detect repeated invalid guesses.
- Define behavior for disconnected clients.
- Define behavior for incomplete evaluations.
- Keep training word lists separate from hidden evaluation lists if desired.

## Original Phase 12: Logging and Replay

- Define a game-log format.
- Record game ID.
- Record difficulty.
- Record each guess in order.
- Record whether each guess was correct.
- Record pattern after each guess.
- Record remaining guesses after each move.
- Record final outcome.
- Add optional timestamps.
- Add a replay utility or endpoint.
- Ensure logs do not expose hidden evaluation words before evaluation completion.

## Original Phase 13: Testing (out-of-scope items)

The other Phase 13 items moved to Phases 3, 4, and 6.

- Test terminal-client integration.
- Test automated bots.
- Test evaluation sessions.
- Test scoring.
- Test leaderboard ordering.

## Original Phase 14: Documentation and Packaging (out-of-scope items)

The other Phase 14 items moved to Phases 2 and 8.

- Document how to use the terminal client.
- Document how to write a student bot.
- Document scoring.
- Document evaluation rules.
- Document leaderboard behavior.

---

# Optional Future Phases

These should not be implemented until the core project is stable.

## Persistent Storage

- [ ] Store games in a database.
- [ ] Store evaluations in a database.
- [ ] Persist leaderboard results.

## Accounts and Authentication

- [ ] Student accounts.
- [ ] API keys or tokens.
- [ ] Authenticated evaluation submissions.

## Tournament Mode

- [ ] Batch evaluation of multiple bots.
- [ ] Scheduled tournaments.
- [ ] Tournament history.
- [ ] Public results page.

## Advanced Bot Analysis

- [ ] Entropy-based guessing.
- [ ] Information-gain strategies.
- [ ] Performance charts.
- [ ] Per-difficulty statistics.
- [ ] Head-to-head bot comparisons.

## Multiplayer

- [ ] Human-vs-human modes.
- [ ] Custom words.
- [ ] Spectator mode.
