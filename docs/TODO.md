# TODO

## Backend architecture review — priority order

Review one item at a time. Agree responsibilities and the smallest useful change before implementation; a checked item means the review/design is agreed, not that refactoring has been completed. Preserve the existing lifecycle, cancellation, validation, and hidden-information safeguards. Backend groundwork precedes the admin dashboard.

**Implementation update:** the agreed architectural tidy-up (items 1–4, 6, and 7, including identity/activation follow-ups) is complete. Configuration is loaded explicitly from environment variables/optional `backend/.env`, dependencies are assembled in `app.py`, and application shutdown owns room/runtime cleanup. All 126 backend, 29 frontend, and 15 launcher tests pass. SQLite/event logging (item 5) and dashboard features are deferred new feature work, not outstanding tidy-up.

- [x] **1. Session/membership ownership and room lifecycle — design direction agreed.** Identify the source of truth for membership and phase; review duplicated user flags, session-context access, preferences/readiness/start, and departure. Agree one owner for existing room-level operations without adding a parallel manager/service stack.
  - **Agreed direction:** reshape the existing room coordinator rather than add another manager; register session contexts alongside connections; keep lobby membership distinct from the human/AI game roster; derive membership flags where practical; make handlers thin and room-level lifecycle operations centrally owned. Implemented in the authorized initial refactor; further structural cleanup remains subject to review.
  - **Role/handler considerations:** prefer one optional backend `Role`, deriving team/spymaster properties. Account for the frontend's duplicated numeric role enums and repeated role checks; preserve the existing wire mapping during backend cleanup and consider frontend consolidation separately. Move authoritative preference/membership mutations out of handlers; retain request decoding and response/error translation at the transport boundary.
  - **Scope:** review/refactor existing behavior only. Dashboard-specific abort/close operations do not exist yet and are deferred to dashboard work; do not design or add them during backend cleanup. Existing completion, departure, disconnect, and last-human disposal remain in scope.
- [x] **2. Game state/rules versus runtime effects — design direction agreed.** Review `CodenamesGame` responsibilities: board generation, rules, snapshots, broadcasts, AI scheduling, replacement, and disposal. Agree a minimal boundary and consistent validation/action outcomes; preserve stale-turn and task-lifetime protections.
  - **Agreed direction:** game owns board, participants, turns, rules, and result; a small game runtime owns AI scheduling/cancellation, broadcasting, and client cleanup. Game operations change state without network/OpenAI dependencies; runtime coordinates effects afterward. Prefer two straightforward objects in the game package, not a service hierarchy, event bus, command framework, or class per action. Preserve turn/revision guards and explicit task ownership. Implemented with synchronous rule operations returning whether state changed, and runtime/public-command validation preserving the current player protocol.
- [x] **3. Connection and delivery abstractions — design direction agreed.** Review the two connection interfaces/adapter, transport-coupled player identity, competing broadcast paths, unused registry methods, and outbound delivery behavior. Decide what can be consolidated or removed.
  - **Agreed direction:** one connection interface (`id`, `send`), no bridging adapter, and one registry associating human connections with session contexts. Player identity is independent of transport; AI players need no fake connection. Share actual delivery/failure handling while room/game code selects recipients and creates recipient-specific, hidden-information-safe snapshots. Failed/slow recipients must not block others or indefinitely stall progression; remove unused registry operations unless needed by the revised design. Implemented with concurrent bounded delivery and serialized sends per connection; no messaging framework. Follow-up cleanup removed the unused connection `close` contract and `Role.all_roles`; WebSocket server construction now takes only the room coordinator and uses its registry rather than accepting a redundant second argument.
- [x] **4. AI execution and resource ownership — design direction agreed.** Review `ClueService`/`GPTAgent`/`ChatGPT`, duplicated AI-player construction, dependency creation, client cleanup, and failure/retry policy. Agree which layers earn their place and one explicit resource owner.
  - **Agreed direction:** game runtime absorbs AI turn orchestration/recovery from `ClueService`; consolidate `GPTAgent`/`ChatGPT` into one wrapper for prompts, provider requests, response parsing/validation, and explicit close. Inject the dependency/factory into the runtime, with one lazily created client per game runtime and runtime-owned cleanup, not a shared pool. Share AI participant construction between startup/takeover. Preserve failed-clue retry, failed-guess notification/pass, task cancellation, and captured-turn checks before applying results. Implemented without a plugin/provider framework.
- [ ] **5. Game-event logging and storage — deferred feature, outside the completed tidy-up.** Define accepted-transition/AI/admin event records, ordering/correlation, safe diagnostics, persistence needs, retention/privacy, and storage-failure behavior. Distinguish a live room registry from durable game history; select the smallest adequate storage approach afterward.
  - **Storage direction:** use lightweight, embedded SQLite for event logging only, via Python's standard-library `sqlite3`; no separate database process/server, ORM, or generic repository framework. Retain events indefinitely by default, with no automatic age-based deletion. Do not persist actual game state, board/state snapshots, serialized runtime objects, or recovery checkpoints; live games remain in memory and are not restored/replayed from the log. Keep event payloads deliberately limited. Define the exact event allowlist, bounded nonblocking write approach, storage-health reporting, and explicit operator deletion/export behavior before implementation; indefinite retention does not mean unbounded in-memory buffering or dashboard responses.
  - **Storage visibility:** show event-log disk usage and a simple size-warning flag in the admin dashboard; account for SQLite sidecar files if used. Expected volume is tens of MB, not a guaranteed cap. Agree a warning threshold during implementation; exceeding it must not automatically delete events or stop gameplay. No storage-management dashboard or automatic retention machinery is needed initially.
- [x] **6. Remaining architectural ceremony and organization — implemented.** Review the async CRUD repository over mutable in-memory objects, inconsistent `services/` layout, static factory, handler-per-command ceremony, and unused owner semantics. Settle naming/module placement after responsibilities are clear, not as a cosmetic first step.
  - **Implemented:** replaced `services/` with `connections.py` (`Connection`, `Session`, `Connections`) and `rooms.py` (`Rooms`). Rooms directly owns live state; lookup/list operations are synchronous, lifecycle operations remain async. Removed repository interfaces/update calls and unused lobby-owner state. Replaced the static game factory with functions and the class-per-command handler package with a single `messages.py` dispatcher/shared context checks. Preserved protocol/error responses and existing lifecycle/race protections. Added regression checks for direct queries, filtering, role filling, and dispatcher errors; no SQLite, dashboard actions, or step-7 startup/configuration redesign.
  - **Follow-up points 2 and 4:** removed duplicate transport identity and session ID aliases; retained the existing player UUID on the wire. Runtime construction now accepts the room ID and starts inactive; one-time `activate()` owns startup flags, revision, initial snapshot delivery, and AI scheduling after room-roster delivery. Added activation/disposal and identity regression tests. Other review suggestions remain deferred.
- [x] **7. Configuration, composition, and final coherence check — implemented.** Review import-time configuration/credential checks and hard-coded dependency construction. Confirm a simple startup/shutdown ownership path, test seams, and an incremental implementation order; identify any missing regression tests before refactoring.
  - **Implemented:** immutable `Settings` and explicit `load_settings()` in `options.py`; process environment overrides optional `backend/.env`, parsed using `python-dotenv`. Required credential name is `OPENAI_API_KEY`; no JSON configuration or old-name compatibility/migration. The key is excluded from settings repr. `app.py` loads settings once, assembles connections/rooms/AI factory, binds the listener, and guarantees room/runtime cleanup and socket closure. AI/model/delay dependencies are explicit, not imported globals/defaults. `Rooms.shutdown()` blocks new starts, retires membership, and disposes runtimes without normal leave/start side effects. The launcher bootstraps dependencies then handles dotenv/prompting through its managed Python, keeping credentials out of public setup output, installer/frontend environments, and command arguments. Added `.env.example`, ignore rules, configuration/import/startup/shutdown tests, and updated setup/port-contract tests; actual ignored credentials were not migrated or deleted.

## General tasks and completed fixes

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

- [x] Fix the backend lifecycle reproductions in [test_lifecycle_reproductions.py](../backend/tests/test_lifecycle_reproductions.py):
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
- [x] Fix the frontend lifecycle reproductions in [lifecycle-timing.test.tsx](../codenames-gpt-ui/tests/lifecycle-timing.test.tsx):
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
