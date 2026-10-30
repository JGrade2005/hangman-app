# Report Notes: Hangman Web App

Draft notes for the 1 to 2 page report. They are bullets to turn into prose, not finished text. Every fact comes from [DEV_LOG.md](DEV_LOG.md), which has the full detail. The reflection section is left for you.

- **Live site:** https://hangman-app-mom6.onrender.com/
- **Repository:** https://github.com/JGrade2005/hangman-app

## 1. Development process

- Built with Claude Code in 8 phases. Each phase followed the same loop:
  1. write the phase's checklist in TODO.md;
  2. implement it;
  3. verify it;
  4. stop and report;
  5. wait for approval before the next phase.
- **Phase 1** was review and planning only, with no code. Claude read the specification, the TODO, the example Cursor transcript and my agentic library, mapped every requirement to a phase, and flagged conflicts for me to decide.
- **Scope decision.**
  - The specification describes a bigger platform (terminal client, bots, evaluation mode, leaderboard, replay), and the provided TODO arrived with all 181 items already checked off from another project.
  - I approved building only the assignment's parts A to E.
  - The TODO was reset and reorganized into the 8 phases: 79 original items in scope, and 102 kept unchanged in an "Out of Scope" section rather than deleted.
- **AI roles:**
  - Opus (the lead model) designed each phase's contract (function names, API fields, status codes), reviewed every diff and fixed review findings.
  - Sonnet subagents wrote most of the code and tests.
  - Haiku subagents independently checked each phase against the spec, the TODO and the brief, and produced a test coverage map.
- **Records:** one commit per phase (I ran every git command myself), plus DEV_LOG.md with prompts, decisions, problems and fixes.

## 2. Implementation

**Game engine** (`game.py`, `word_manager.py`; pure Python, no Flask)
- `HangmanGame` stores only the hidden word and the guessed letters. The pattern, incorrect letters, remaining guesses and status are recalculated on every call, so they cannot go stale.
- `guess()` checks in a fixed order: invalid input, then game over, then a duplicate. A rejected guess changes nothing.
- `to_state()` adds `word` only after the game ends. The class's repr hides the word, so it cannot leak into logs.
- Word lists are the course's lists (188, 211 and 234 words). They are cleaned, deduplicated and validated as ASCII letters. Words are picked with `secrets.choice`.

**Server and API** (`server.py`, `game_store.py`)
- Three routes from the spec: create (201 plus a `Location` header), get state, and guess.
- Errors are JSON with exact status codes: 400, 404, 405, 409, 413, and 500 without a traceback.
- Games live in memory, keyed by a random `uuid4` ID. One lock covers each whole operation, so concurrent guesses cannot both pass the duplicate check.
- An LRU-ordered dict gives 1-hour idle expiry and a 10,000-game cap cheaply.
- Every response gets a Content-Security-Policy and `nosniff` header. API responses are marked not cacheable.

**Web client** (`static/`; plain HTML, CSS and JavaScript, no framework)
- **What's on the page:**
  - a difficulty select and a New game button;
  - a 6-part SVG hangman;
  - letter cells for the word;
  - the remaining guesses, guessed letters and incorrect letters;
  - an A to Z on-screen keyboard plus physical-keyboard input;
  - win and loss messages;
  - light and dark themes, working down to 320px wide.
- The browser holds only the game ID and the server's last reply, and it redraws everything from that reply. The game ID travels in the URL (`/api/games/<id>/guess`); the body carries only the letter.
- **Slow-network handling:** one guess at a time per game, replies from an old game ignored, a 90 s timeout, a "server waking up" notice, and a clear message when a game has expired.

## 3. Testing

- **292 automated tests in about 20 s:** 267 pytest tests across the engine, words, store, API and served page, plus 25 Playwright tests in headless Chromium.
- **Browser tests:**
  - a win by clicking and a loss by typing at every difficulty, with the whole UI checked after every guess;
  - a new game without reload;
  - an expired game and an unreachable server;
  - slow-network races;
  - keyboard focus;
  - a 320px phone layout;
  - full games on the real word lists.
- **Hidden word, checked at every level:** the engine (state keys), the API (the exact field set while playing) and the browser (a watcher fails any test if a playing response contains `word`).
- **Mutation check:** 15 bugs were planted in a copy of the app, and each was caught by the test meant for it.
- **Coverage map:** Haiku traced every testing requirement in the brief to the tests that cover it, reading the test bodies. The gaps it found were closed.
- **Manual playthrough:** I played Easy, Medium and Hard in the browser and confirmed each used the right word list.

## 4. Deployment

- Render free web service, created from a `render.yaml` Blueprint. Gunicorn settings live in `gunicorn.conf.py` (1 worker, 4 threads, bound to `0.0.0.0` on `PORT`). `.python-version` pins 3.12, because Render now defaults to 3.14.
- **Before deploying:** built a clean venv from `requirements.txt` only and started it exactly as Render would (`PORT=10000`). curl and browser games passed.
- **Live checks over HTTPS:**
  - full games at every difficulty, with each word confirmed from the right list;
  - every error code;
  - the security headers;
  - no word in any playing response;
  - the Playwright check on desktop, phone and dark mode.
- **Free tier:** the service sleeps after 15 idle minutes. Cold start measured: _(see DEV_LOG, Phase 7)_.

## 5. Challenges and fixes (pick one or two)

1. **Why the server must run one worker.** Games live in process memory, and each Gunicorn worker is a separate process. I measured it locally: with 2 workers, 8 of 100 lookups for existing games returned 404; with 1 worker, 0 did. The failure looked random, because Linux sends most connections to one worker. Fix: 1 worker with 4 threads, set in `gunicorn.conf.py`, with the reason in a comment.
2. **Bugs that only appear on a slow network.**
   - Locally, replies take milliseconds, so the first browser tests passed.
   - A Haiku code review found these real bugs:
     - starting a new game during a pending guess left the new game's keys locked;
     - there was no timeout, so a stalled request froze the page;
     - a repeated letter on the physical keyboard caused a server error;
     - the keys flickered on every guess;
     - keyboard users lost their focus.
   - I reproduced them by adding an 800 ms delay inside the test server, fixed them in `app.js`, and turned them into permanent browser tests.
3. **A hidden-word "leak" that wasn't one.** The class lists contain the word "easy" in the Easy list, so the word's text also appeared in the `difficulty` field during play. Instead of deleting words, I showed it reveals nothing: a test proves two different 4-letter Easy words produce identical states. Lesson: test that outputs can't be told apart, not that a string is absent.
4. **A concurrency test that could never fail.** The first lock test still passed with the lock removed. I replaced it with a slow stand-in game that makes overlap visible, and confirmed it fails 3 of 3 times without the lock.

## 6. Representative prompts

1. **Kickoff** (sets the process): "Build and deploy the Hangman web app ... For each phase: write the phase's TODO checklist, implement it, checking items off in TODO.md, verify it, stop and report ... Don't start the next phase until every item in the current one is checked off and I approve." This led to the 8-phase plan, the scope decision and the reorganized TODO.
2. **Manual verification before moving on:** "So far everything works properly. All 3 difficulties are working and have correct words. Continue onto phase 6." This recorded my own browser playthrough as part of the testing evidence.
3. **Understanding the design:** "For the site implementation, how is the game state tracked on the server side and on the player side? Game ID and status isn't sent in the payload of the HTTP get and post requests, so how is this information tracked on both ends?" The answer: the ID travels in the URL, not the body; the server holds the real state; the browser holds only the ID and the last reply. That explanation is now in the README's "How it works" section.

## 7. Reflection

_To be written by you._
