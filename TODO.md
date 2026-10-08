# TODO

- [ ] Lint the project, covering the frontend and backend.
- [ ] Set up GitHub Actions CI, including runs after PR merges into main.
- [ ] Review the failing reproduction tests:
  - [ ] AI turns stall when the response contains too few guesses.
  - [ ] AI turns stall when invalid guesses exhaust the response.
  - [ ] AI guess-request failures leave the turn stuck.
  - [ ] AI clue-request failures only print errors instead of notifying players.
  - [ ] Disconnected players remain in the active game roster.
  - [ ] Broadcasts fail when they target a disconnected player's socket.
  - [ ] Lobby departures do not broadcast the updated player roster.
  - [ ] Empty preferences requests restart an active game.
  - [ ] Ready players cannot become unready.
  - [ ] Unnamed players are excluded from the game-start readiness check.
  - [ ] Lobbies with no named players can start.
  - [ ] Repeated guesses on the same tile consume additional guesses.
  - [ ] String clue counts are accepted and mutate game state.
  - [ ] Negative clue counts are accepted.
  - [ ] Fractional clue counts are accepted.
  - [ ] Boolean clue counts are accepted.
  - [ ] Clue counts exceeding the board size are accepted.
  - [ ] Whitespace-only clue words are accepted.
  - [ ] Non-string clue words cause errors after partially mutating state.
  - [ ] Repeated lobby creation leaves the user in multiple lobbies.
  - [ ] Joining another lobby leaves the previous membership intact.
  - [ ] Joining the same lobby twice duplicates the player.
  - [ ] Disconnect cleanup leaves ghost memberships after repeated creation.
  - [ ] Frontend and backend default WebSocket ports disagree.
  - [ ] Lobby callbacks retain the pre-hydration player identity.
  - [ ] Lobby callbacks retain an old identity after it changes.
  - [ ] Lobby callbacks navigate using an outdated lobby ID.
  - [ ] Player updates crash when the current player is missing.

## Endgame and timing bugs

- [ ] Review the backend lifecycle reproductions in [test_lifecycle_reproductions.py](backend/tests/test_lifecycle_reproductions.py):
  - [ ] Winning guesses schedule another AI clue request: final own-team tile, opponent's final tile, and assassin, for either team.
  - [ ] Clue generation requests AI output before checking whether the game is finished.
  - [ ] AI guess loops continue submitting ignored guesses after victory.
  - [ ] Internal pass-turn calls mutate a completed game's turn, clue, and guess count.
  - [ ] Empty preferences requests replace completed games and erase the result.
  - [ ] Pending old AI tasks broadcast obsolete boards and winners after game replacement.
  - [ ] Last-human departure deletes the lobby without terminating pending AI work.
  - [ ] A second connection's preferences request replaces a game while startup delivery is pending.
  - [ ] Turn advancement during a broadcast can schedule clue generation for an operative.
  - [ ] A failed broadcast recipient prevents the next AI turn from starting.
  - [ ] Creating or joining a new lobby after completion retains readiness and in-game flags.
  - [ ] Name confirmation in a new room starts a game using readiness from the previous game.
  - [ ] Post-start role preferences can claim an AI-filled role and expose hidden tile teams.
- [ ] Review the frontend lifecycle reproductions in [lifecycle-timing.test.tsx](codenames-gpt-ui/tests/lifecycle-timing.test.tsx):
  - [ ] Batched roster/state delivery leaves the game without its current player.
  - [ ] Batched startup messages leave the UI on the lobby screen.
  - [ ] Full game snapshots do not update the current player from their roster.
  - [ ] Lobby mount sends pregame preferences even after requesting navigation into the game.
  - [ ] Returning home replays a previously handled lobby-joined response.
  - [ ] Queued role preferences are sent after the lobby screen that requested them unmounts.
  - [ ] Development Strict Mode duplicates mutation-shaped lobby initialization.
  - [ ] An obsolete socket's close event marks its open replacement as closed.
  - [ ] An obsolete socket's late frame overwrites current state.
  - [ ] Tile clicks send guesses after victory or when the player is off turn.
  - [ ] Clue submission remains enabled when the winner is known.
  - [ ] Rejected actions produce console output rather than visible error feedback.
- [ ] Add remaining regression coverage for stale commands accepted on a later matching-role turn, deep-link/session resumption, and actions while disconnected.

## Non-bug improvements and design decisions

- [ ] Define how long finished rooms and results should be retained, with an explicit leave/return-to-home flow.
- [ ] Consider an explicit rematch flow that keeps players together and starts a fresh game only on request.
- [ ] Consider revealing the complete board for postgame review.
- [ ] Define the policy for a player leaving an occupied role: pause, AI replacement, forfeit, or game termination.
- [ ] Add connection status and reconnect/resynchronization UX.
- [ ] Add pending-action indicators and consistent feedback while waiting for server responses.
- [ ] Replace untyped WebSocket messages with a shared, typed protocol and document its phase rules.
- [ ] Reduce broadcast noise by making read-only snapshot requests requester-specific.
