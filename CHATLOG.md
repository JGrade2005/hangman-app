# Chat Log: Prompts Used to Build the Hangman Web App

These are the prompts I gave the AI coding agent (Claude Code), in order, quoted word for word. Each one has a short note on what it led to. The full detail of every decision, problem and fix is in [DEV_LOG.md](DEV_LOG.md).

- **Tool:** Claude Code, with Opus 5.5 as the lead agent.
- **Subagents:**
  - Sonnet subagents wrote most of the code and tests.
  - Haiku subagents checked each phase against the spec and the TODO.
- **Date:** all prompts were on 2026-10-29, in one session.

## Most representative prompts

These three show the main parts of how I worked: setting the process, checking the result myself, and making sure I understood the design.

### 1. The kickoff prompt (sets the process)

The opening prompt set up the whole workflow: what to read first, the five required parts, eight phases with a stop-and-approve gate after each one, rules for conflicts, and a running development log. The full text is under [Prompt 1](#1-kickoff-build-and-deploy-the-hangman-web-app) below.

> "For each phase: write the phase's TODO checklist → implement it, checking items off in TODO.md → verify it → **stop and report** (what's done, what you verified, open questions). Don't start the next phase until every item in the current one is checked off and I approve."

**Why it matters:** the agent could never run ahead. The first phase was planning only, which surfaced the scope conflict (the spec describes a much larger platform than the assignment) for me to decide before any code was written.

### 2. Confirming the work myself before moving on

> "So far everything works properly. All 3 difficulties are working and have correct words. continue onto phase 6"

**Why it matters:** I played the app in the browser at every difficulty and checked the words came from the right lists before approving the testing phase. My manual check was recorded as part of the testing evidence, alongside the automated tests.

### 3. Asking how the design works, not just for code

> "For the site implementation, how is the game state tracked on the server side and on the player side. Game ID and status isn't sent in the payload of the HTTP get and post requests, so how is this information tracked on both ends?"

**Why it matters:** the answer explained the core design.
- The game ID travels in the URL path, not the request body.
- The server stores each game's word and guesses, and recalculates the status on every request.
- The browser keeps only the ID and the server's last reply, and never sends a status.

That explanation became the "How it works" section of the README.

## All prompts, in order

| # | Phase | Prompt (verbatim) | What it led to |
|---|---|---|---|
| 1 | 1. Review and plan | The kickoff prompt (full text below) | The agent read my agentic library, the spec, the TODO and the example Cursor transcript. It flagged conflicts (scope, a TODO that arrived fully checked off, a nested git repo) and presented an 8-phase plan with recommended answers. |
| 2 | 2. Setup | "Yes, use defaults" | Approved the recommended answers. Set up the folders, venv, pinned requirements, word lists, `.gitignore` and `git init`. The TODO was reorganized into 8 phases with nothing deleted. |
| 3 | 3. Game engine | "Start Phase 3" | Built `word_manager.py` and `game.py` with unit tests. A review found the words "easy" and "medium" in their own lists, and a test proved this reveals nothing. |
| 4 | 3. Game engine | "Once you finish phase 3, can you give a good commit message covering all the changes" | A commit message for the first commit, plus one for the parent course repo. |
| 5 | 3. Game engine | "Can you give me the git command for commiting the hangmanapp stuff" | Ready-to-run `git add` and `git commit` commands. From then on, every phase report ended with them. |
| 6 | 3. Game engine | (Pasted the output of a git warning: "warning: There are too many unreachable loose objects; run 'git prune' ...") | The warning came from the parent course repo (9,551 orphaned file snapshots, no commits lost). The agent gave the cleanup commands. |
| 7 | 4. Flask API | "Continue onto the next phase" | Built `game_store.py` and `server.py` with API tests. A concurrency test that could not fail was replaced with one proven to fail without the lock. |
| 8 | 5. Web client | "Start Phase 5" | Built the HTML, CSS and JS client. It was checked in a real browser, and five slow-network bugs found by an independent review were fixed. |
| 9 | 6. Local testing | "So far everything works properly. All 3 difficulties are working and have correct words. continue onto phase 6" | Added 25 Playwright browser tests, ran the app under Gunicorn, measured why it needs a single worker, and mapped every testing requirement to its tests. |
| 10 | 7. Deployment | "Start Phase 7" | Wrote `render.yaml`, `gunicorn.conf.py` and `.python-version`, simulated the Render build locally, and gave me the exact GitHub and Render steps. |
| 11 | 7. Deployment | "https://hangman-app-mom6.onrender.com/ Here is the deployed website." | Verified the live site over HTTPS: every difficulty, every error code, no hidden word during play, and browser games on desktop and phone. |
| 12 | 7. Deployment | "For the site implementation, how is the game state tracked on the server side and on the player side. Game ID and status isn't sent in the payload of the HTTP get and post requests, so how is this information tracked on both ends?" | An explanation of URL-based game IDs, server-held state, and a browser that keeps only the ID and the last reply. |
| 13 | 8. Submission | "Continue onto the next phase" | Wrote the README, the report notes and the session log. A fresh install from GitHub, following the README, passed. |
| 14 | 8. Submission | "In this app, where are the GET http requests?" | GET serves the page and its files, and reads one game's state. The browser rarely sends it itself, because every POST already returns the updated game. |
| 15 | 8. Submission | "what phases are left?" | Only the last Phase 8 item remained, plus my final push and the report reflection. |
| 16 | 8. Submission | "For this report, can you include a CHATLOG.md of the representative prompts used in this assignment?" | This file. |

## Prompt 1 in full

### 1. Kickoff: build and deploy the Hangman web app

<details>
<summary>Show the full kickoff prompt</summary>

```text
# Task: Build and deploy the Hangman web app

## Source materials (read these first, in this order)
1. `~/agenticLibrary/`: my standard working procedures (documentation conventions, subagent rules, workflow). Follow them throughout; they override your defaults.
2. `class14-hangmanapp/Specifications.md`: the source of truth for app behavior.
3. `class14-hangmanapp/TODO.md`: the implementation checklist.
4. `class14-hangmanapp/` cursor transcript: an example of how a similar implementation went. Use it for approach and pitfalls only. Don't copy it.

## Required components
**A. Game engine (Python, no dependency on Flask or the browser)**
- Random word selection from word lists for Easy, Medium and Hard
- Validates letter guesses; rejects repeated and invalid input
- Tracks correct guesses, incorrect guesses and remaining incorrect guesses
- Produces the current word pattern (e.g. `_ A _ _ _`)
- Detects wins and losses; refuses further guesses once a game is over

**B. Flask server and REST API**
- `POST /api/games`: create a game (takes difficulty)
- `GET /api/games/{game_id}`: get the current game state
- `POST /api/games/{game_id}/guess`: submit a letter
- JSON in and out, unique game IDs, separate state per game, request validation, correct HTTP status codes (e.g. 201, 400, 404, 409)
- **The hidden word never leaves the server while a game is active.** It may be revealed only after the game ends.

**C. Web client (HTML, CSS and JavaScript, served by Flask)**
- Choose a difficulty, start a game, guess by clicking buttons or typing on the keyboard
- Show the word pattern, the letters guessed, the remaining incorrect guesses, a hangman drawing (SVG or HTML) that grows with each miss, and a win/lose message
- Start a new game without reloading the page
- All game logic goes through `fetch()` to the API. The browser has no game engine of its own and never holds the hidden word.

**D. Testing**
- Automated tests (pytest) for the engine and the API: all three difficulties, correct and incorrect guesses, repeated and invalid guesses, win, loss, a new game after a finished one, invalid API requests, and the hidden word not exposed during play
- A browser check that the UI updates correctly after each guess (manual, or with Playwright)

**E. Deployment**
- Deploy to Render (or another suitable host) at a public HTTPS URL. A user must be able to play a complete game in the browser with nothing installed.

## Phases
For each phase: write the phase's TODO checklist → implement it, checking items off in TODO.md → verify it → **stop and report** (what's done, what you verified, open questions). Don't start the next phase until every item in the current one is checked off and I approve.

1. **Review and plan** (Step 1): read all the materials and map every spec requirement and TODO item to a phase. Show me the plan before writing any code.
2. **Initialize the project** (Step 2): folder structure, virtual environment, `requirements.txt`, word lists, git init, `.gitignore`.
3. **Game engine** (A), with its unit tests.
4. **Flask server and API** (B), with API tests.
5. **Web client** (C).
6. **Local testing** (Step 4 / D): full test run plus a browser playthrough at each difficulty.
7. **Deployment** (Step 5 / E): gunicorn, Render config, push to GitHub. Tell me exactly which steps need my accounts (GitHub, Render), wait while I do them, then check the live URL end to end.
8. **Submission package**: finalize the README and TODO.md, and draft the report notes (see below).

## Rules
- Subagents and documentation: follow `~/agenticLibrary` exactly.
- Conflicts: Specifications.md and the requirements above win over the TODO and the transcript. Flag any conflict to me instead of guessing.
- Keep a running `DEV_LOG.md`: key prompts I gave you, decisions, problems hit and how they were fixed. I'll use it for my report.

## Definition of done (submission checklist)
**GitHub repo contains:** the engine and Flask server; the HTML/CSS/JS frontend; the word lists; the original Specifications.md; the updated TODO.md; `requirements.txt` and the deployment config; the tests; and a README with instructions for running locally.
**Deployed URL:** live and working (it must stay up during grading).
**Report support:** from DEV_LOG.md, draft notes for a 1–2 page report covering development process, implementation (engine, server, API, UI), testing, deployment, at least one challenge and its fix, and 2–3 representative prompts. Leave the reflection section for me to write.
```

</details>
