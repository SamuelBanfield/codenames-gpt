# TODO

- [ ] Lint the project, covering the frontend and backend.
- [ ] Set up GitHub Actions CI, including runs after PR merges into main.
- [x] Fix the original reproduction cases:
  - [x] AI turns stall when the response contains too few guesses.
  - [x] AI turns stall when invalid guesses exhaust the response.
  - [x] AI guess-request failures leave the turn stuck.
  - [x] AI clue-request failures only print errors instead of notifying players.
  - [x] Disconnected players remain in the active game roster.
  - [x] Broadcasts fail when they target a disconnected player's socket.
  - [x] Lobby departures do not broadcast the updated player roster.
  - [x] Empty preferences requests restart an active game.
  - [x] Ready players cannot become unready.
  - [x] Unnamed players are excluded from the game-start readiness check.
  - [x] Lobbies with no named players can start.
  - [x] Repeated guesses on the same tile consume additional guesses.
  - [x] String clue counts are accepted and mutate game state.
  - [x] Negative clue counts are accepted.
  - [x] Fractional clue counts are accepted.
  - [x] Boolean clue counts are accepted.
  - [x] Clue counts exceeding the board size are accepted.
  - [x] Whitespace-only clue words are accepted.
  - [x] Non-string clue words cause errors after partially mutating state.
  - [x] Repeated lobby creation leaves the user in multiple lobbies.
  - [x] Joining another lobby leaves the previous membership intact.
  - [x] Joining the same lobby twice duplicates the player.
  - [x] Disconnect cleanup leaves ghost memberships after repeated creation.
  - [x] Frontend and backend default WebSocket ports disagree.
  - [x] Lobby callbacks retain the pre-hydration player identity.
  - [x] Lobby callbacks retain an old identity after it changes.
  - [x] Lobby callbacks navigate using an outdated lobby ID.
  - [x] Player updates crash when the current player is missing.

## Endgame and timing bugs

- [x] Fix the backend lifecycle reproductions in [test_lifecycle_reproductions.py](backend/tests/test_lifecycle_reproductions.py):
  - [x] Winning guesses schedule another AI clue request: final own-team tile, opponent's final tile, and assassin, for either team.
  - [x] Clue generation requests AI output before checking whether the game is finished.
  - [x] AI guess loops continue submitting ignored guesses after victory.
  - [x] Internal pass-turn calls mutate a completed game's turn, clue, and guess count.
  - [x] Empty preferences requests replace completed games and erase the result.
  - [x] Pending old AI tasks broadcast obsolete boards and winners after game replacement.
  - [x] Last-human departure deletes the lobby without terminating pending AI work.
  - [x] A second connection's preferences request replaces a game while startup delivery is pending.
  - [x] Turn advancement during a broadcast can schedule clue generation for an operative.
  - [x] A failed broadcast recipient prevents the next AI turn from starting.
  - [x] Creating or joining a new lobby after completion retains readiness and in-game flags.
  - [x] Name confirmation in a new room starts a game using readiness from the previous game.
  - [x] Post-start role preferences can claim an AI-filled role and expose hidden tile teams.
- [x] Fix the frontend lifecycle reproductions in [lifecycle-timing.test.tsx](codenames-gpt-ui/tests/lifecycle-timing.test.tsx):
  - [x] Batched roster/state delivery leaves the game without its current player.
  - [x] Batched startup messages leave the UI on the lobby screen.
  - [x] Full game snapshots do not update the current player from their roster.
  - [x] Lobby mount sends pregame preferences even after requesting navigation into the game.
  - [x] Returning home replays a previously handled lobby-joined response.
  - [x] Queued role preferences are sent after the lobby screen that requested them unmounts.
  - [x] Development Strict Mode duplicates mutation-shaped lobby initialization.
  - [x] An obsolete socket's close event marks its open replacement as closed.
  - [x] An obsolete socket's late frame overwrites current state.
  - [x] Tile clicks send guesses after victory or when the player is off turn.
  - [x] Clue submission remains enabled when the winner is known.
  - [x] Rejected actions produce console output rather than visible error feedback.
- [x] Add regression coverage for AI takeover/retry, startup departures, capacity changes during cleanup, stale turn commands, and disconnected actions.
- [ ] Add deep-link/session-resumption coverage.

## Non-bug improvements and design decisions

- [x] Keep finished rooms/results until the last human leaves, with an explicit leave/return-to-home flow.
- [ ] Consider an explicit rematch flow that keeps players together and starts a fresh game only on request.
- [ ] Consider revealing the complete board for postgame review.
- [x] Replace a departed human's active role with AI while other humans remain; dispose of the game when the last human leaves.
- [ ] Add connection status and reconnect/resynchronization UX.
- [x] Add pending-action indicators and consistent feedback while waiting for server responses.
- [ ] Replace untyped WebSocket messages with a shared, typed protocol and document its phase rules.
- [x] Reduce broadcast noise by making read-only snapshot requests requester-specific.
