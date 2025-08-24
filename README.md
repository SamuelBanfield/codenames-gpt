# codenames-gpt

## Overview

Codenames-GPT is a Python-based implementation of the popular board game "Codenames" using OpenAI's GPT4. The game allows players and AI to play together. When all human players in a lobby are ready, any remaining roles will be filled in by ChatGPT.

A [demo](https://sambanfield.com/codenames/) is available.

The repository contains both the backend python websocket server, and the NextJS front end.

## How to play

To begin, either create or join a lobby then select a team and role. Once all human players in the lobby have selected a role and clicked, ready the game will begin and any open roles will be filled in by the AI.

If you are a Spy Master, on your turn you must select a word that links to as many of the words of your colour as possible. Make sure not to link to the other team's words or the assassin.

If you are a guesser, try to guess the word's linking to the clue supplied.  If you guess wrong, or you run out of guesses your turn will end.

## Setup

To run the backend, create a `backend/.properties.json` file containing the following properties:

* openaiKey - An open AI key
* gptModel - Which model to use, e.g. `gpt-4o`
* guessDelay - (Optional) The time in seconds that the AI will delay before supplying a clue or guess. The AI will otherwise play incomprehinsibly quickly

Then the server can be start using:

```sh
cd backend
python run.py
```

or run as a docker image:

```sh
cd backend
docker build -t codenames-backend .
docker run -e OPENAI_KEY="<key>" -p 8000:8000 codenames-backend
```

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

## Contact

For any questions or suggestions, please open an issue or contact me
