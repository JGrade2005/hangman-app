const GAMES_PATH = "/api/games";
const SLOW_START_MS = 3000;
// Long enough for a sleeping free-tier server to wake, short enough that a
// stalled request cannot freeze the page.
const REQUEST_TIMEOUT_MS = 90000;
const LETTERS = [..."abcdefghijklmnopqrstuvwxyz"];
const MESSAGE_KINDS = ["win", "loss", "error"];
const KEY_LABELS = { correct: "in the word", incorrect: "not in the word" };
const IGNORED_TARGETS = new Set(["SELECT", "INPUT", "TEXTAREA"]);

const MESSAGES = {
  starting: "Starting a new game.",
  waking:
    "The server may be waking up after being idle. " +
    "This can take up to a minute.",
  started: "New game started. Guess a letter.",
  expired: "This game has expired. Press New game to start another.",
  unreachable:
    "Could not reach the server. Check your connection and try again.",
  timeout: "The server took too long to respond. Please try again.",
  generic: "Something went wrong. Please try again.",
  noGame: "No game in progress",
  noLetters: "None yet",
};

const elements = {
  difficulty: document.getElementById("difficulty"),
  newGame: document.getElementById("new-game"),
  message: document.getElementById("message"),
  drawing: document.getElementById("drawing"),
  word: document.getElementById("word"),
  remaining: document.getElementById("remaining"),
  guessed: document.getElementById("guessed-letters"),
  incorrect: document.getElementById("incorrect-letters"),
  keyboard: document.getElementById("keyboard"),
};
const parts = [...elements.drawing.querySelectorAll(".part")];
const keys = LETTERS.map(createKey);

// pendingGuess holds the game_id of the pending guess, so a slow reply
// from an old game cannot lock the keys of a new one.
const state = { game: null, creating: false, pendingGuess: null };

// status is 0 when there was no usable API response.
class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function api(path, payload) {
  const options =
    payload === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        };
  let response;
  try {
    response = await fetch(path, {
      ...options,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut = error.name === "TimeoutError";
    throw new ApiError(timedOut ? MESSAGES.timeout : MESSAGES.unreachable, 0);
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(MESSAGES.generic, 0);
  }
  if (!response.ok) {
    const message =
      typeof data?.error === "string" ? data.error : MESSAGES.generic;
    throw new ApiError(message, response.status);
  }
  return data;
}

function describeError(error) {
  return error instanceof ApiError ? error.message : MESSAGES.generic;
}

// A response for a game the player has since left must not be applied.
function isCurrent(gameId) {
  return state.game !== null && state.game.game_id === gameId;
}

function canGuess() {
  return (
    state.game !== null &&
    state.game.status === "playing" &&
    !state.creating &&
    state.pendingGuess !== state.game.game_id
  );
}

async function startGame() {
  if (state.creating) return;
  state.creating = true;
  render();
  showMessage(MESSAGES.starting);
  // Free hosting sleeps when idle, so the first request can be very slow.
  const wakingTimer = setTimeout(
    () => showMessage(MESSAGES.waking),
    SLOW_START_MS,
  );
  try {
    state.game = await api(GAMES_PATH, {
      difficulty: elements.difficulty.value,
    });
    showMessage(MESSAGES.started);
  } catch (error) {
    showMessage(describeError(error), "error");
  } finally {
    clearTimeout(wakingTimer);
    state.creating = false;
    render();
  }
}

async function submitGuess(letter) {
  if (!canGuess()) return;
  if (letterOutcome(state.game, letter) !== null) {
    showMessage(`You already guessed ${letter.toUpperCase()}.`);
    return;
  }
  const gameId = state.game.game_id;
  state.pendingGuess = gameId;
  try {
    const game = await api(`${GAMES_PATH}/${gameId}/guess`, { letter });
    if (isCurrent(gameId)) acceptGuess(game, letter);
  } catch (error) {
    if (isCurrent(gameId)) await rejectGuess(error, gameId);
  } finally {
    if (state.pendingGuess === gameId) state.pendingGuess = null;
    render();
  }
}

function acceptGuess(game, letter) {
  state.game = game;
  announceGuess(game, letter);
  if (game.status !== "playing") elements.newGame.focus();
}

async function rejectGuess(error, gameId) {
  if (error.status === 404) {
    expireGame();
    return;
  }
  showMessage(describeError(error), "error");
  if (error.status === 409) await refreshGame(gameId);
}

function expireGame() {
  state.game = null;
  showMessage(MESSAGES.expired, "error");
}

async function refreshGame(gameId) {
  try {
    const game = await api(`${GAMES_PATH}/${gameId}`);
    if (!isCurrent(gameId)) return;
    state.game = game;
    if (game.status !== "playing") announceResult(game);
  } catch (error) {
    if (!isCurrent(gameId)) return;
    if (error.status === 404) expireGame();
    else showMessage(describeError(error), "error");
  }
}

function announceResult(game) {
  const word = game.word.toUpperCase();
  if (game.status === "won") {
    showMessage(`You won! The word was ${word}.`, "win");
  } else {
    showMessage(`Out of guesses. The word was ${word}.`, "loss");
  }
}

function announceGuess(game, letter) {
  const shown = letter.toUpperCase();
  if (game.status !== "playing") {
    announceResult(game);
  } else if (game.incorrect_letters.includes(letter)) {
    showMessage(`No, ${shown} is not in the word.`);
  } else {
    showMessage(`Yes, ${shown} is in the word.`);
  }
}

function showMessage(text, kind = "") {
  elements.message.textContent = text;
  elements.message.classList.remove(...MESSAGE_KINDS);
  if (kind) elements.message.classList.add(kind);
}

function render() {
  const game = state.game;
  renderDrawing(game);
  renderWord(game);
  renderStatus(game);
  renderKeyboard(game);
  // aria-disabled instead of disabled keeps focus on the button while a
  // game is being created. startGame ignores clicks in the meantime.
  elements.newGame.setAttribute("aria-disabled", String(state.creating));
}

function renderDrawing(game) {
  const missed = game ? game.incorrect_letters.length : 0;
  for (const part of parts) {
    part.classList.toggle("shown", Number(part.dataset.part) <= missed);
  }
  elements.drawing.setAttribute(
    "aria-label",
    `Hangman drawing, ${missed} of ${parts.length} parts`,
  );
}

function wordCells(game) {
  if (!game) return [];
  const found = game.pattern.split(" ");
  const lost = game.status === "lost";
  const letters = lost ? [...game.word] : found;
  return letters.map((letter, index) => ({
    text: letter === "_" ? "" : letter.toUpperCase(),
    missed: lost && found[index] === "_",
  }));
}

function describeWord(cells) {
  if (cells.length === 0) return "Word: no game yet";
  const spoken = cells.map(({ text, missed }) => {
    if (text === "") return "blank";
    return missed ? `${text} (missed)` : text;
  });
  return `Word: ${spoken.join(" ")}`;
}

function createCell({ text, missed }) {
  const cell = document.createElement("span");
  cell.className = missed ? "cell missed" : "cell";
  cell.textContent = text;
  return cell;
}

function renderWord(game) {
  const cells = wordCells(game);
  elements.word.replaceChildren(...cells.map(createCell));
  elements.word.setAttribute("aria-label", describeWord(cells));
}

function formatLetters(letters) {
  if (letters.length === 0) return MESSAGES.noLetters;
  return letters.map((letter) => letter.toUpperCase()).join(", ");
}

function describeRemaining(game) {
  if (!game) return MESSAGES.noGame;
  const { remaining_guesses: left, max_incorrect_guesses: max } = game;
  return `Incorrect guesses left: ${left} of ${max}`;
}

function renderStatus(game) {
  const guessed = game ? game.guessed_letters : [];
  const incorrect = game ? game.incorrect_letters : [];
  elements.remaining.textContent = describeRemaining(game);
  elements.guessed.textContent = formatLetters(guessed);
  elements.incorrect.textContent = formatLetters(incorrect);
}

function createKey(letter) {
  const key = document.createElement("button");
  key.type = "button";
  key.className = "key";
  key.dataset.letter = letter;
  key.textContent = letter.toUpperCase();
  return key;
}

function letterOutcome(game, letter) {
  if (!game || !game.guessed_letters.includes(letter)) return null;
  return game.incorrect_letters.includes(letter) ? "incorrect" : "correct";
}

function renderKey(key, game, playable) {
  const outcome = letterOutcome(game, key.dataset.letter);
  key.classList.toggle("correct", outcome === "correct");
  key.classList.toggle("incorrect", outcome === "incorrect");
  key.disabled = !playable || outcome !== null;
  if (outcome) {
    const label = `${key.textContent}, ${KEY_LABELS[outcome]}`;
    key.setAttribute("aria-label", label);
  } else {
    key.removeAttribute("aria-label");
  }
}

function renderKeyboard(game) {
  // Keys stay enabled while a guess is pending so they do not flicker.
  const playable =
    game !== null && game.status === "playing" && !state.creating;
  const focused = keys.indexOf(document.activeElement);
  for (const key of keys) renderKey(key, game, playable);
  if (focused !== -1 && keys[focused].disabled) focusNextKey(focused);
}

// Disabling the focused key would drop keyboard users back to the page top.
function focusNextKey(from) {
  const ordered = [...keys.slice(from + 1), ...keys.slice(0, from)];
  const next = ordered.find((key) => !key.disabled);
  (next ?? elements.newGame).focus();
}

function handleKeyClick(event) {
  const key = event.target.closest(".key");
  if (key) submitGuess(key.dataset.letter);
}

function handleKeydown(event) {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
  if (event.isComposing) return;
  // Typing a letter in a focused select would change its option instead.
  if (IGNORED_TARGETS.has(event.target.tagName)) return;
  if (!/^[a-z]$/i.test(event.key)) return;
  submitGuess(event.key.toLowerCase());
}

function init() {
  elements.keyboard.replaceChildren(...keys);
  render();
  elements.newGame.addEventListener("click", startGame);
  elements.keyboard.addEventListener("click", handleKeyClick);
  document.addEventListener("keydown", handleKeydown);
}

init();
