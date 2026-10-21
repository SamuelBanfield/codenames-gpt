# codenames-gpt

## Overview

Codenames-GPT is a Python-based implementation of the popular board game "Codenames" using OpenAI's GPT4. The game allows players and AI to play together. When all human players in a lobby are ready, any remaining roles will be filled in by ChatGPT.

A [demo](https://sambanfield.com/codenames/) is available.

The repository contains both the backend python websocket server, and the NextJS front end.

See [Documentation](docs/README.md) for the architecture overview, prioritized issues, TODO, and implementation plans.

## How to play

To begin, either create or join a lobby then select a team and role. Once all human players in the lobby have selected a role and clicked, ready the game will begin and any open roles will be filled in by the AI.

If you are a Spy Master, on your turn you must select a word that links to as many of the words of your colour as possible. Make sure not to link to the other team's words or the assassin.

If you are a guesser, try to guess the word's linking to the clue supplied.  If you guess wrong, or you run out of guesses your turn will end.

Finished games stay read-only until players leave using **Return to lobby selection**. If a human leaves an active game, AI takes over their role while other humans remain. The lobby and its AI work are cleaned up when the last human leaves. Failed AI clue requests can be retried using **Retry AI turn**.

## Setup

### One-command local development

With Python 3.12+ and Node.js 20.19+ (or 22.12+) installed, run from the repository root:

```sh
python dev.py
```

The launcher installs dependencies on first run, starts both servers, and opens **http://localhost:3000/codenames**. Later runs reuse the installed dependencies unless their requirements change. Press **Ctrl+C** to stop both servers.

It uses `OPENAI_API_KEY` from the environment or `backend/.env`. If neither supplies a key, it prompts once and saves it in that Git-ignored `.env` file. Environment variables override `.env` values. The launcher installs dependencies before reading `.env`, using its managed Python environment; no global dotenv installation is needed. Use `python dev.py --no-browser` to skip opening a browser, or `--port 3001 --backend-port 8001` if the default ports are occupied.

### Manual setup

Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY`, or supply the environment variables directly. `.env` is optional and never overrides the real process environment. Values are literal (no `${...}` interpolation).

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Required | OpenAI credential; validated at startup, not import time |
| `HOST` | `0.0.0.0` | Backend bind address |
| `WEBSOCKET_PORT` | `8000` | Backend port |
| `GPT_MODEL` | `gpt-4o` | OpenAI model |
| `GUESS_DELAY` | `0` | Nonnegative whole seconds between AI guesses; launcher defaults to `1` if unset |

The old `.properties.json` format and `OPENAI_KEY` name are no longer supported. Existing local credential files are not migrated or deleted automatically. Keep `.env` private; it is excluded from Git and Docker build contexts.

Start the backend with:

```sh
cd backend
python -m pip install -r requirements.txt
python run.py
```

or run as a docker image:

```sh
cd backend
docker build -t codenames-backend .
docker run -e OPENAI_API_KEY -p 8000:8000 codenames-backend
```

Export `OPENAI_API_KEY` in your shell before the Docker run command (or inject it through your deployment secret mechanism). The local `.env` file is not bundled into the image.

The UI can be started with:

```sh
cd codenames-gpt-ui
npx next dev
```

or run as a docker image:

```sh
cd codenames-gpt-ui
docker build -t codenames-ui .
docker run -e NEXT_PUBLIC_WEBSOCKET_URL="<url>" -p 3000:3000 codenames-ui
```

## Tests

Use Python 3.12 and Node.js 20.19+ (or 22.12+). Tests mock OpenAI and do not require a real API key or a running server.

Launcher tests, from the repository root (install backend test dependencies in the Python environment you use for tests):

```sh
python -m pip install -r backend/requirements-dev.txt
python -m unittest discover -s tests -v
```

From `backend/`:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

From `codenames-gpt-ui/`:

```sh
npm ci
npm test
```

The frontend port-contract test requires `python` on PATH; set `PYTHON` to another executable, such as `python3`, if needed.

The regression suites cover game lifecycle, validation, and UI message timing.

## Contact

For any questions or suggestions, please open an issue or contact me
