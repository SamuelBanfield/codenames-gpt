# Review reproduction tests

This branch contains executable regression specifications for all nine numbered
code-review findings. Tests assert the expected correct behavior and deliberately
fail on the current application. They are ordinary failures, not skipped or
`xfail` tests, so a future fix can make them pass without rewriting assertions.

## Setup and commands

Use Python 3.12 and Node.js 20.19+ (or 22.12+). No real OpenAI credentials, live
WebSocket server, browser installation, or network access is required to run the
tests after dependencies are installed.

From `backend/`:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

The pytest configuration is now `backend/pytest.ini`, uses the correct `[pytest]`
section, and enables async test support. `tests/conftest.py` provides a dummy key
before application imports and replaces the OpenAI client with a mock. The two
existing AI tests now patch the current `codenames.gpt.chat_gpt` module path.

From `codenames-gpt-ui/`:

```sh
npm ci
npm test -- --reporter=verbose
npx tsc --noEmit --incremental false
npm run lint
```

Vitest runs the actual React hooks and WebSocket provider under jsdom. The port
contract test evaluates the real Python backend configuration in a subprocess,
with property-file reads and configuration overrides excluded. Python must be
available as `python` on PATH, or set the `PYTHON` environment variable to the
Python executable to use (for example, `python3`).

The test suites return a nonzero exit code while the reproductions fail.

## Coverage

| Finding | Test cases | Expected behavior |
| --- | --- | --- |
| 1. AI turns stall | `test_01_*` (4 failing cases) | Exhausted/partially valid responses and failed guess requests pass the turn; failed clue requests notify humans rather than only printing an error. |
| 2. Disconnected players remain | `test_02_*` (3 failing cases) | WebSocket cleanup removes the departed player from the game; later broadcasts succeed for remaining players; lobby departures publish an updated roster. |
| 3. Preferences restart games | `test_03_*` (1 failing case) | An empty preferences request preserves the active game object, board, and revealed tiles. |
| 4. Readiness is incorrect | `test_04_*` (3 failing cases) | Explicit `False` clears readiness; unnamed joiners and lobbies with no named players cannot start. |
| 5. Duplicate guesses consume guesses | `test_05_*` (1 failing case) | Two identical routed guess messages reveal one tile and consume one guess. |
| 6. Invalid clues mutate state | `test_06_*` (7 failing cases) | String, negative, fractional, boolean, and oversized counts, blank words, and non-string words yield validation errors without mutation. |
| 7. Multiple lobby memberships | `test_07_*` (4 failing cases) | Repeated create/join requests cannot leave multiple memberships; joining twice is idempotent; disconnect removes ghost memberships. |
| 8. Default ports disagree | `tests/websocket-defaults.test.tsx` (1 failing case) | The URL actually passed to the browser WebSocket constructor uses the backend's default port. |
| 9. Stale lobby callback | `tests/lobby-identity.test.tsx` (4 failing cases) | Hydrated/changed identity and changed lobby routes use current values; missing players do not crash the hook. |

Backend reproduction tests use a deterministic board and mocked AI responses.
They exercise real game transitions, message routing, lobby membership, and
connection cleanup rather than substituting those implementations.

For AI failure handling, these tests specify passing after failed guessing and
notifying human players after failed clue generation. For membership changes,
either rejecting a switch or removing the previous membership is acceptable.

## Verified results on this branch

| Check | Result |
| --- | --- |
| Full backend suite | **23 intentional reproduction failures, 6 passes** |
| Frontend suite | **5 intentional reproduction failures, 2 passes** |
| TypeScript | Pass |
| Frontend lint | Pass with the 5 existing application hook-dependency warnings |

The passing backend cases include all four existing tests and two controls: an
empty AI response already passes its turn, and valid clues/distinct guesses
progress normally. The two frontend controls verify an unchanged identity/route
and an explicitly configured WebSocket URL, including cleanup on unmount.

To run just the restored original backend tests, from `backend/`:

```sh
python -m pytest -m "not reproduction"
```

To run the passing controls, from each respective directory:

```sh
python -m pytest tests/test_review_reproductions.py -k control
npm test -- -t "control:"
```
