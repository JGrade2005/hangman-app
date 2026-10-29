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
