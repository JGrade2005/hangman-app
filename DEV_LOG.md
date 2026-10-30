# Development Log: Hangman Web App (Class 14)

Running log of key prompts, decisions, problems and fixes. Newest phase at the bottom.

Tooling: Claude Code (Opus 5.5 as lead). Subagent routing follows `~/agenticlibrary`: Sonnet writes code, Haiku reads and verifies against the spec and TODO, Opus designs contracts and reviews.

---

## Phase 1: Review and plan (2026-10-29)

**Key prompt (kickoff):** "Build and deploy the Hangman web app ... For each phase: write the phase's TODO checklist, implement it, checking items off in TODO.md, verify it, stop and report. Don't start the next phase until every item in the current one is checked off and I approve." Required parts: A engine, B Flask REST API, C web client, D tests, E deployment. Spec and the brief win over the TODO and the transcript; flag conflicts instead of guessing.

**What was read:**
- `~/agenticlibrary` (README, context.md, recent class12, class13 and class14 session logs).
- `Specification.md`, `TODO.md`.
- `cursor_transcript.md` (2,299 lines), summarized by a Haiku subagent for approach and pitfalls.

**Findings:**
- `TODO.md` arrived with all 180 core items already checked, copied from the transcript's finished project. Nothing is built in this folder yet.
- `TODO.md` refers to `Hangman_Project_Specification.md`; the real file is `Specification.md`.
- The spec covers more than the brief: terminal client, bots, evaluation mode, scoring, leaderboard, logging and replay.
- `TODO.md` says to update the spec for any deviation, but the submission needs the original spec.
- The folder sits untracked inside the public `JGrade2005/CSE4095_2026` repo, so a plain `git init` would nest a repo.
- The class word lists from class12 (188 easy, 211 medium, 234 hard) are clean: lowercase, alphabetic, no duplicates.

**Pitfalls taken from the transcript:**
- In-memory games need a single Gunicorn worker, or games scatter across processes and return random 404s.
- Render free tier sleeps after about 15 minutes idle, which wipes in-memory games.
- Bot tests were tuned to random outcomes; tests here inject fixed words instead.
- A generic "could not connect" message hid a real SSL error; the UI should show the server's actual error.
- Phases 8 to 13 (evaluation, leaderboard, replay) went far past a playable game.

**Decisions (user approved all recommended defaults, prompt: "Yes, use defaults"):**
- Scope: brief parts A to E only. The terminal client, bots, evaluation, scoring, leaderboard, and logging/replay are out of scope.
- TODO.md: reorganized around the 8 phases with every box reset. No original item deleted.
- Git: a standalone repo in this folder, ignored by the parent `CSE4095_2026` repo. The user does every commit and push.
- Browser test: Playwright as a dev-only dependency, with Claude in Chrome as the fallback.
- Others: the spec stays original (deviations go in the README), plain JS instead of TypeScript, duplicate guesses return 409.

---

## Phase 2: Initialize the project (2026-10-29)

**Done:**
- Folders `words/`, `static/`, `tests/`. Python 3.12.3 venv in `.venv/`.
- `requirements.txt` pins Flask 3.1.3 and gunicorn 26.2.0. `requirements-dev.txt` adds pytest 9.2.0 and Playwright 1.64.1.
- Word lists copied from the class12 bot examples (the course's public lists).
- `.gitignore` covers the venv, caches, Playwright output, agent state, and `cursor_transcript.md` (reference material, not project source).
- `git init -b main`. The parent repo's `.gitignore` now ignores this folder, so it is not added as an embedded repo.
- `TODO.md` reorganized (Opus). `progress.py` writes `PROGRESS.md` (Sonnet).

**Decisions:**
- Branch `main`, the GitHub default for new repos, instead of the parent repo's `master`.
- Only top-level dependencies are pinned. That is enough for a two-package app and keeps the file readable.
- Playwright headless Chromium installed and launched in WSL without sudo, so the planned fallback to Claude in Chrome is not needed for automated tests.

**Verified:**
- A Haiku audit script compared the old and new TODO. All 181 original core items appear exactly once with unchanged text and the correct origin tag: 79 in scope, 102 out of scope. All 18 optional items are unchanged. The Phase 1 count was corrected from "about 110 of 180" out of scope to the real 102 of 181.
- The venv imports Flask 3.1.3, pytest 9.2.0 and gunicorn 26.2.0. pytest runs, with no tests yet.
- The copied word lists are byte-identical to the class lists.
- `git status` in the new repo lists 11 intended files. `.venv/`, `.claude-flow/` and `cursor_transcript.md` are ignored. The parent repo shows only its `.gitignore` change.
- No em dashes in any new file.

**Status:** Phase 2 is 12/12. Overall 15/115 (13%), 2/8 phases.

---

## Phase 3: Game engine (2026-10-29)

**Key prompt:** "Start Phase 3" (game engine with unit tests, no Flask dependency).

**Contract (designed by Opus, built by Sonnet):**
- `word_manager.py`: `WordManager` loads, cleans and deduplicates the three lists and fails at startup if a list is missing or empty. `random_word()` uses `secrets.choice`. `normalize_difficulty()` accepts any case and surrounding spaces, and raises `InvalidDifficultyError` (a `ValueError`) for anything else.
- `game.py`: `HangmanGame` with a private word and no public getter. Status (`playing`/`won`/`lost`) is computed from the guesses on every read, so it can never go stale. `guess()` checks in a fixed order: invalid input, then game over, then duplicate. A rejected guess changes nothing. `to_state()` returns JSON-ready data and adds `word` only after the game ends. `start_game()` ties the two modules together.

**Decisions:**
- Three guess errors (`InvalidGuessError`, `DuplicateGuessError`, `GameOverError`) under one base class, so the API can map them to 400, 409 and 409 without reading message text.
- Validation comes before state checks, so a malformed request always gets the same answer whether or not the game has ended.
- `HangmanGame` is a plain class with a custom `__repr__`. A dataclass's default repr would print the hidden word into server logs or a debug traceback.
- Letters must be ASCII. `str.isalpha()` alone accepts letters like "é".

**Built (Sonnet):** `word_manager.py` (about 100 lines), `game.py` (about 165 lines), `pytest.ini`, and 125 unit tests in `tests/test_word_manager.py` and `tests/test_game.py`.

**Problem found in verification (good report challenge):**
- **Problem:** the Haiku check swept all 633 words. The class lists contain the word "easy" in `easy.txt` and "medium" in `medium.txt`. In those games, the hidden word's text appears in the `difficulty` field of the state while the game is still playing. `easy.txt` also contains "hard". A test that searches the response text for the word would fail by chance, about 1 game in 200.
- **Analysis:** this is not a real leak. The difficulty is the client's own input and is the same for every game at that level, so it carries no information about the word. Removing the words would hide the symptom and change the course lists.
- **Fix:** keep the field. Add a test proving that two different 4-letter Easy words ("easy" and "fish") produce identical states and reprs while playing. The disclosure rule is tested by key absence plus this test, never by substring search.
- **Lesson:** "the secret is not in the output" means the output carries no information about the secret. Test that the outputs cannot be told apart, not that a string is missing.

**Other review fixes (Opus):**
- A bare string passed as a word list loaded as single letters ("cat" became c, a, t). It now raises `TypeError`.
- Word files are read as `utf-8-sig`. A UTF-8 BOM from a Windows editor made the first word invalid, so it was dropped silently.
- `HangmanGame` validates and normalizes its difficulty instead of accepting any value.
- Added a test for a new game after a finished one (brief D). The Haiku check marked it missing.

**Verified:**
- 134 tests pass in 0.13 s.
- Neither module imports Flask or anything web-related.
- No lines over 79 characters and no em dashes.
- The Haiku agent independently checked 64 requirements (36 TODO, 14 spec, 14 brief): 56 met. Every partial or missing item traced to the four issues fixed above, apart from "server is authoritative", which can only be checked once the server exists in Phase 4.

**Status:** Phase 3 is 32/32. Overall 47/116 (40%), 3/8 phases.

---

## Phase 4: Flask server and REST API (2026-10-29)

**Key prompt:** "Continue onto the next phase" (the Flask server and API, with API tests).

**Contract (designed by Opus, built by Sonnet):**
- `game_store.py` (no Flask): `GameStore` keeps games in an `OrderedDict` ordered by last use, guarded by one lock. IDs come from `uuid4().hex`. Games idle for more than 1 hour expire, and a 10,000-game cap evicts the least recently used.
- `server.py`: the `create_app(word_manager, store=...)` factory lets tests inject fixed words. A module-level `app` serves Gunicorn. The three spec routes return `{"game_id", ...state}`, and `word` appears only after the game ends.
- Status codes:

| Status | When |
|---|---|
| 201 | Create, with a `Location` header |
| 200 | Get or guess |
| 400 | Body is not a JSON object, or a bad difficulty or letter |
| 404 | Unknown or expired game, or unknown route |
| 405 | Wrong method |
| 409 | Duplicate guess, or a guess after the game ends |
| 413 | Body over 1 KB |
| 500 | Unexpected error (generic message, no traceback) |

- Every error is JSON `{"error": ...}`. All `/api/` responses carry `Cache-Control: no-store`.

**Decisions:**
- **One lock around each whole store operation.** Lookup, guess and snapshot all run under the lock, so two concurrent guesses of the same letter cannot both pass the duplicate check. This matters because Gunicorn runs 4 threads.
- **LRU ordering.** Expiry and the cap can pop from the front of the ordered dict instead of scanning every game. This is the same structure as the LRU cache interview problem.
- **Engine exception classes mapped to status codes.** Mapping the exception classes, never bare `ValueError`, means a real bug still surfaces as a 500 instead of being disguised as a user error.
- **Debug mode is off when running `python server.py`.** The Werkzeug debugger can run arbitrary code if it is ever exposed.

**Built (Sonnet):** `game_store.py` (110 lines), `server.py` (115 lines), 22 store tests, and 66 API tests.

**Problems found and fixed (Opus):**
- **The concurrency test could not fail.** The agent's 20-thread duplicate-guess test still passed with the lock removed (3 of 3 runs, and 0 of 150 in the Haiku check), because the engine's check-then-append window is too narrow under the GIL. I added `test_store_runs_one_engine_call_at_a_time`, which uses a slow stand-in game and records overlapping calls. With the lock removed, it failed 3 of 3 runs. Lesson: a concurrency test has to be shown to fail without the protection, or it only gives false confidence.
- **Doubled slashes bypassed the JSON errors.** `/api/games//guess` got an HTML 308 redirect, because Werkzeug merges slashes and routing redirects skip the error handlers. Setting `url_map.merge_slashes = False` makes it a JSON 404.
- **`/api` (no trailing slash) lacked `Cache-Control: no-store`.** Fixed the path check.
- The hidden-word API test now asserts the exact key set of every playing response, not just that `word` is absent.

**Verified:**
- 225 tests pass in 0.5 s.
- curl against `python server.py` played a full game at each difficulty (easy "field", medium "darling", hard "questionable", all losses to a frequency-order guesser). The word was never present while playing, and a guess after the end gave 409.
- curl also returned JSON 400, 404 and 405 errors, with `Cache-Control: no-store`.
- The Haiku check: 44 of 45 items met. The partial item was "JSON consistently": Flask's automatic OPTIONS reply (empty body, accepted as is) and the redirect fixed above. Its fuzz ran 180 real games and found 0 responses with extra keys while playing.

**Notes for the README (Phase 8):**
- A wrong Content-Type gets 400 rather than 415, because the brief lists 400.
- The 10,000-game cap can evict an active game that has gone unused for the longest time.
- Expired games are removed lazily, on the next create or access.

**Status:** Phase 4 is 25/25. Overall 72/118 (61%), 4/8 phases.

---

## Phase 5: Web client (2026-10-29)

**Key prompt:** "Start Phase 5" (HTML, CSS and JS client served by Flask, all game logic through `fetch()`).

**Contract (designed by Opus, built by Sonnet):**
- `static/index.html`, `style.css`, `app.js` (an ES module, no framework, no build step). `GET /` serves the page.
- The browser keeps only the current `game_id` and the last server state, and renders everything from that state. It decides nothing about the game itself. The only local logic is ignoring keys that are not A to Z.
- The page has a 6-part SVG hangman (one part per miss), the word as letter cells, remaining guesses, guessed and incorrect letters, a 26-key on-screen keyboard (guessed keys disabled and marked), physical-keyboard input, and win and loss messages that reveal the word from the final server response.
- It handles errors: it shows the server's `error` text, treats a 404 as an expired game (for example after a Render restart), shows a message when the network is down, and after 3 seconds explains that the server may be waking up.

**Decisions:**
- **One request at a time, and stale responses are ignored.** A slow reply from an old game must not overwrite a new one.
- **Key presses are ignored while the difficulty `<select>` has focus.** Typing a letter there changes the selected option, so it would otherwise also send a guess.
- **A Content-Security-Policy (`default-src 'self'`) and `nosniff` header on every response.** As a result, the page has no inline scripts, styles or handler attributes. Even if text were ever injected into the page, it could not run as script.
- **The difficulty select does not restart a game.** It only applies to the next New game, so a misclick cannot throw away a game in progress.

**Built (Sonnet):**
- `static/index.html` (61 lines), `style.css` (about 310), `app.js` (344), `favicon.svg`.
- 41 tests in `tests/test_web.py`: page and assets served, security headers present, no inline code that the CSP would block, 6 drawing parts, no word list shipped to the browser.

**Browser verification (Opus, Playwright scripts in the session scratchpad):**
- 4 full games through the real UI by clicking and by typing, on desktop, a 360px phone and dark mode. Each one checked:
  - No API response contained `word` while playing.
  - The drawing matched the server's miss count after every guess.
  - Guessed keys were disabled, and focus moved to New game at the end.
  - Typing in the focused select sent no guess.
- A fixed-word server for a forced win, the 12-letter word at 320 and 375px, the server stopped mid-game ("could not reach the server", still playable), and a restart with an empty store ("game expired", keys disabled, New game recovers).
- 800 ms of server-side latency on guesses, to recreate Render's slow network (see below).

**Problems found and fixed:**
- **Long words wrapped on phones.** The 12-letter hard words used fixed 36px cells (476px in all), so "questionable" broke onto two lines. Cells now shrink to fit one row (`flex: 0 1`, `aspect-ratio`). The first attempt shrank them far too much, because the row was sized to its contents. Setting `width: 100%` fixed that.
- **CSP blocks Playwright's `wait_for_function`.** It polls by evaluating strings, which `default-src 'self'` forbids. The first check passed only because its conditions were already true on the first try. Waits now use `expect(locator)`. This confirms the CSP is enforced, and the Phase 6 test must follow the same rule.
- **A leftover test server gave false results.** A crashed check left a server on its port, so the next run's "server down" step was testing the leftover server. The scripts now refuse a port that is already in use and always stop their server in `finally`. Servers are killed by PID, never with `pkill -f`, which earlier killed my own shell.
- **Slow-network bugs found by the Haiku code review.** On local servers replies take milliseconds, so the first browser run could not see these. All are fixed in `app.js` and confirmed with real latency:
  - Clicking New game during a pending guess left the new game's keys locked until the old reply came back. The pending guess is now tied to its `game_id`.
  - There was no request timeout, so a stalled request froze the page. A 90-second `AbortSignal.timeout` now covers a cold start.
  - A letter repeated on the physical keyboard was sent to the server and came back as a red 409. It now shows "You already guessed Z." without a request.
  - Every key greyed out during each guess, which flickers on real latency. Keys now stay enabled, and input is ignored while a guess is pending.
  - Keyboard users lost focus when their key or New game was disabled. Focus now moves to the next key, and New game uses `aria-disabled` so it keeps focus.
  - A non-JSON 404 (from a proxy) was treated as an expired game. A 404 on the refresh after a 409 now expires the game. A game that ended through a 409 now shows its result. Typing during IME composition is ignored.
- **Lesson:** a UI tested only against localhost has never seen latency. Adding a deliberate server delay exposes the race conditions real users would hit.

**Verified:** 266 tests pass. All three browser checks pass after the fixes. The Haiku code review found 40 of 42 items met, and its 2 partial items were the timeout and the duplicate-key bugs fixed above.

**Status:** Phase 5 is 23/23. Overall 95/120 (79%), 5/8 phases.

---

## Phase 6: Local testing (2026-10-29)

**Key prompt:** "So far everything works properly. All 3 difficulties are working and have correct words. Continue onto phase 6."

**Manual browser playthrough (user):** played games at Easy, Medium and Hard in the browser and confirmed each one works with words from the right list.

**Gunicorn, production start command (Opus):**
- `gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 server:app` started the `gthread` worker. The log showed no errors and a clean shutdown.
- curl played a full game at each difficulty (easy "small", medium "dispute", hard "exquisite"). There were 0 responses with `word` while playing, and a guess after the end gave 409. The page served the CSP and `nosniff` headers.
- The Playwright check played 4 full browser games against Gunicorn (desktop, phone, dark mode, click and keyboard input) with no problems.

**Why Gunicorn must run a single worker (measured):**

| Setup | State requests for a game that exists | 404s |
|---|---|---|
| `--workers 2 --threads 1` | 100 (10 games, 10 GETs each) | 8 |
| `--workers 1 --threads 4` | 100 (same test) | 0 |

- Each worker process has its own memory, so a game created in one worker does not exist in the other.
- The failure rate is low and random because Linux hands most connections to one worker. That makes it look like an intermittent bug rather than a design limit.
- Threads share memory, so concurrency comes from threads, protected by the store's lock.
- Scaling to several workers or instances would need shared storage such as Redis or a database.

**Browser end-to-end suite (Sonnet, reviewed by Opus):**
- `tests/test_ui.py` (616 lines): 15 test functions, 21 cases, about 14 s. Pytest now registers a `ui` marker, so `pytest -m "not ui"` skips the browser tests. Without Chromium installed they skip with an install hint.
- Each test gets its own live Flask server in a thread on a random free port. Fixed words (apple, banana, questionable), a fake clock to expire games, and a server-side guess delay to simulate latency.
- A watcher records every API response. Every playing response must have exactly the 8 playing keys and no `word`. The check fails if it recorded nothing, so it cannot pass vacuously. A normal game must also produce no console or page errors, which is where a CSP violation would show up.
- Coverage:
  - a win (by clicking) and a loss (by typing) at each difficulty, checking the drawing, message, keys, remaining guesses and letter lists after every guess;
  - repeated letters revealed;
  - a new game after a finished one, with no page reload;
  - the select does not restart a game in progress;
  - a duplicate key sends no request;
  - typing in the select sends no guess;
  - an expired game;
  - an unreachable server;
  - slow-network races;
  - keyboard focus;
  - the 12-letter word on a 320px phone.
- **Mutation check:** the agent planted 15 deliberate bugs in a scratch copy of the app (for example keys disabled during a guess, the word leaking while playing, a page reload on New game, the word wrapping on a phone). Each one was caught by the test written for it.
- **Fixed while writing:** `server.shutdown()` waited 0.5 s per test for its default poll interval. `poll_interval=0.02` halved the suite time, from 27 s to 14 s.

**Full run:** 287 tests pass (266 Python plus 21 browser) in about 14 s, on two consecutive runs by Opus and three by Sonnet. Running three copies of the suite at once also passed, so the tests are not flaky.

**Open UX choice (for the user):** a letter typed while the previous guess is still pending is ignored silently. This is deliberate, to keep one request at a time. The alternative is a short "Waiting for the last guess" message.

**Test coverage map (Haiku, checked against the test bodies, not just their names):**

| Brief requirement | Engine | Store / API | Browser |
|---|---|---|---|
| All three difficulties | `test_start_game_for_each_difficulty` | `test_create_game[easy/medium/hard]` | `test_win_by_clicking_keys`, `test_loss_by_typing_letters` (each per difficulty) |
| Correct and incorrect guesses | `test_correct_guess_reveals_every_occurrence`, `test_incorrect_guess_costs_a_guess` | same names in `test_api.py` | `test_word_cells_and_label_follow_each_guess` |
| Repeated guesses | `test_duplicate_guess_raises_and_changes_nothing` | `test_duplicate_guess_is_a_conflict`, `test_concurrent_duplicate_guesses_succeed_once` | `test_repeated_letter_on_the_keyboard_sends_no_request` |
| Invalid guesses | `test_invalid_guess_raises_and_changes_nothing` | `test_invalid_letter_is_rejected`, `test_guess_rejects_bad_bodies` | `test_non_letter_keys_send_no_guess` |
| Win and loss | `test_win_without_misses`, `test_loss_after_sixth_miss` | `test_winning_game_reveals_the_word`, `test_losing_game_reveals_the_word` | win and loss tests above |
| New game after a finished one | `test_new_game_after_finished_game` | `test_new_game_after_a_finished_one` | `test_new_game_after_a_loss_resets_the_board_without_reloading` |
| Invalid API requests | n/a | `test_create_game_rejects_bad_requests`, `test_wrong_method_is_a_json_405`, `test_get_unknown_game_is_not_found` | `test_expired_game_shows_a_message_and_a_new_game_works` |
| Hidden word not exposed during play | `test_word_is_never_in_state_until_game_ends` | `test_word_is_hidden_until_the_game_ends` | `test_word_stays_hidden_until_the_game_ends`, plus the leak watcher in every browser test |
| Browser UI updates after each guess | n/a | n/a | `test_win_by_clicking_keys` and `test_loss_by_typing_letters` check the whole UI after every guess |

**Gaps the map found, now closed (Opus):**
- No browser test pressed non-letter keys. Added `test_non_letter_keys_send_no_guess` (digits, punctuation, F2, arrows).
- The browser tests used only injected words. Added `test_shipped_app_plays_a_full_game_with_the_real_lists` (per difficulty), which serves the real module-level `app` and checks that the revealed word is in that difficulty's list.
- The page's difficulty options were not tied to the server. Added `test_difficulty_options_match_the_server`.
- Two tests checked less than their names claimed:
  - `test_create_game_ignores_extra_keys` now guesses "a" to tell "apple" apart from the injected "zebra".
  - `test_real_app_creates_games_from_the_word_lists` now plays until the end and checks the word against the real list.
- Two names were narrowed to what their bodies prove:
  - `test_no_list_words_of_six_or_more_letters_ship_to_the_browser`
  - `test_word_matching_its_difficulty_name_reveals_nothing`
- The em-dash test contained a literal em dash. It now uses `"—"`, so no project file contains one.

**Final Phase 6 run:** 292 tests (267 Python plus 25 browser) pass in about 17 s, on two consecutive runs.

**Status:** Phase 6 is 8/8. Overall 103/122 (84%), 6/8 phases.

---

## Phase 7: Deployment (2026-10-29)

**Key prompt:** "Start Phase 7" (gunicorn, Render config, push to GitHub, with clear hand-off steps for anything that needs the user's accounts).

**Render facts, rechecked from the current docs (render.com/docs, fetched today):**
- New services default to Python 3.14.8. A `.python-version` file may give major.minor (`3.12`). The `PYTHON_VERSION` environment variable must be a full version and takes precedence over the file.
- Blueprint: `render.yaml` at the repo root, with `runtime: python` (`env` is deprecated), `plan: free`, and `autoDeployTrigger: commit` (`autoDeploy` is deprecated).
- The app must bind to `0.0.0.0` on `$PORT` (default 10000). The docs do not say whether the start command runs in a shell, so the port is read in Python instead.
- Free web services:
  - spin down after 15 minutes without traffic, and take about a minute to spin up;
  - get 750 instance hours per workspace per month;
  - run on 512 MB and 0.1 CPU;
  - have an ephemeral filesystem;
  - "might restart a Free web service at any time";
  - only one instance.

**Decisions:**
- **`gunicorn.conf.py` holds the bind address, 1 worker, 4 threads and the access log,** and the start command is just `gunicorn server:app`. The config reads `PORT` in Python, so it works whether or not Render expands `$PORT`. The one-worker reason sits next to the setting.
- **`.python-version` pins 3.12,** matching local development (3.12.3), instead of Render's 3.14 default.
- **Service name `hangman-app`, region `virginia`.** The name matches the GitHub repo, and Virginia is the closest US region to Connecticut.
- **Health check `/`.** It serves the page, so a broken static setup also fails the deploy.
- **Restarts are already handled.** Free-tier restarts and sleeps wipe the in-memory games. The client turns the resulting 404 into "This game has expired", and its 90 s request timeout covers a one-minute cold start.

**Render build simulated locally:**
- A clean Python 3.12 venv got `pip install -r requirements.txt` only, which installs 8 packages and no test tools.
- `PORT=10000 gunicorn server:app` came up on `0.0.0.0:10000` with the `gthread` worker and an access log. `/` returned 200.
- curl played a full game at each difficulty (easy "group", medium "triumph", hard "exaggerate") with 0 leaks. The Playwright check passed.

**User steps (accounts):** the user created the public GitHub repo `JGrade2005/hangman-app`, pushed (head `0adf4d9`; the Phase 6 tests went in with this deployment commit because `git add .` staged them), and deployed on Render.

**Live URL:** https://hangman-app-mom6.onrender.com/ (the name `hangman-app` was taken, so Render added the suffix `-mom6`).

**Live verification (Opus):**
- HTTPS with a valid certificate (curl TLS verify result 0). `http://` redirects to `https://` with a 301. The response headers show `x-render-origin-server: gunicorn` behind Cloudflare.
- `live_check.py` (scratchpad) found no problems:
  - the page and its assets return 200, with the CSP and `nosniff` headers;
  - a full game at each difficulty;
  - every revealed word came from the right list (easy "rise", "large"; medium "careful", "throw"; hard "inextricable", "irresolution");
  - no `word` key in any playing response;
  - 409 after a game ends, 409 for a duplicate, 400 for a bad difficulty, the wrong content type, malformed JSON or a two-letter guess;
  - 404 JSON for an unknown game or route, 405 JSON for the wrong method, 413 for an oversized body;
  - `Cache-Control: no-store` on the API;
  - 0 of 30 lookups of finished games lost, so a single worker is serving.
- The Playwright check against the live site played 4 full games (desktop clicking, desktop keyboard, a 360px phone, dark mode) with no problems. Phone keys are 44px tall, and "substantiate" fits on one row.
- **Problem in my own check script:** it first reported the CSP, `nosniff` and `Location` headers as missing. Cloudflare sends lowercase header names, and the script had copied the headers into a plain `dict`, which made lookups case-sensitive. Using urllib's header object, which is case-insensitive, fixed it. **Lesson:** HTTP header names are case-insensitive, so never compare them as plain dict keys.

**Status:** Phase 7 is 8/8. Overall 111/123 (90%), 7/8 phases.

---

## Phase 8: Submission package (2026-10-29)

**Key prompts:**
- "For the site implementation, how is the game state tracked on the server side and on the player side? Game ID and status isn't sent in the payload of the HTTP get and post requests, so how is this information tracked on both ends?"
  - Answer: the ID travels in the URL path. The server's store maps the ID to the game (word plus guesses), and status is recalculated on each request. The browser keeps only the ID and the last reply, and never sends status.
  - This explanation became the README's "How it works" section.
- "Continue onto the next phase."

**Done (Opus):**
- `README.md`:
  - live URL, features, how to run locally (Linux, macOS and Windows) and how to play;
  - project structure and how it works;
  - REST API tables for routes, state fields and errors, plus a real example session captured from a local server with the word fixed to "apple";
  - testing (per-file counts) and deployment;
  - differences from the spec, and known limitations.
- `REPORT_NOTES.md`: notes for the report covering process, implementation, testing and deployment, four challenges to choose from, and three representative prompts. The reflection is left for the user.
- A session log in `~/agenticlibrary/sessions/2026-10-29-class14-hangmanapp/` (`session.md` and `chatlog.md`).

**Fresh-install check (Haiku):**
- Cloned the public repo over HTTPS into an empty folder and followed the README literally. All 5 steps passed:
  1. install;
  2. the page at :5000;
  3. the example session (every status code and error message matched);
  4. `pytest` (292 passed, and 267 with `-m "not ui"`; without Chromium the browser tests skip with the install hint);
  5. Gunicorn at :8000.
- Every file listed in the README exists, and every test count matches `--collect-only`.

**Fixes from the fresh-install check:**
- **Gunicorn listened on `0.0.0.0` even locally,** so a local run was reachable from the network. `gunicorn.conf.py` now binds `0.0.0.0` only when `PORT` is set (Render); otherwise it uses `127.0.0.1:8000`. Checked both ways. Render behavior is unchanged.
- **The README now uses `python3.12 -m venv`.** Plain `python3` can be a newer version on other machines.
- **The README mentions `playwright install --with-deps chromium`** for fresh Linux machines.
- **The project structure lists `pytest.ini` and `progress.py`,** and the error examples now match the output byte for byte.
- The README itself was not on GitHub yet. That is expected until the final commit.

**Correction:** the final test split is 267 Python tests plus 25 browser tests (292 in total). An earlier report said 266 plus 26.
