import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLobbyLogic } from "../app/[lobbyId]/lobby/hooks/useLobbyLogic";

const session = vi.hoisted(() => ({
  playerId: null as string | null,
  lastMessage: undefined as unknown,
  send: vi.fn(),
  // Keep the router stable, as it is during ordinary identity updates.
  router: { push: vi.fn(), replace: vi.fn() },
}));

vi.mock("@/app/playerIdProvider", () => ({
  usePlayer: () => ({ playerId: session.playerId }),
}));
vi.mock("@/app/wsProvider", () => ({
  useWS: () => ({ send: session.send, lastMessage: session.lastMessage }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => session.router }));

function player(uuid: string, name: string, inGame = false) {
  return { uuid, name, ready: false, role: 0, inGame, inLobby: true };
}

describe("finding 9: lobby identity and route changes", () => {
  beforeEach(() => {
    session.playerId = null;
    session.lastMessage = undefined;
    vi.clearAllMocks();
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => vi.restoreAllMocks());

  it("uses the current identity after hydration rather than the mount-time identity", () => {
    const { result, rerender } = renderHook(() => useLobbyLogic("lobby-one"));
    session.playerId = "assigned-player";
    session.lastMessage = {
      serverMessageType: "playerUpdate",
      players: [player("assigned-player", "Alice")],
    };

    // This throws today because the callback still searches for playerId === null.
    expect(() => rerender()).not.toThrow();
    expect(result.current.player.name).toBe("Alice");
  });

  it("selects the new identity when an existing identity changes", () => {
    session.playerId = "old-player";
    const { result, rerender } = renderHook(() => useLobbyLogic("lobby-one"));
    session.playerId = "new-player";
    session.lastMessage = {
      serverMessageType: "playerUpdate",
      players: [player("old-player", "Old"), player("new-player", "New")],
    };

    rerender();

    expect(result.current.player.name).toBe("New");
  });

  it("navigates to the current lobby after the route parameter changes", () => {
    session.playerId = "assigned-player";
    const { rerender } = renderHook(({ lobbyId }) => useLobbyLogic(lobbyId), {
      initialProps: { lobbyId: "old-lobby" },
    });
    rerender({ lobbyId: "new-lobby" });
    session.lastMessage = {
      serverMessageType: "playerUpdate",
      players: [player("assigned-player", "Alice", true)],
    };

    rerender({ lobbyId: "new-lobby" });

    expect(session.router.replace).toHaveBeenCalledWith("/new-lobby/game");
  });

  it("handles an update that does not contain the current player without crashing", () => {
    session.playerId = "assigned-player";
    const { rerender } = renderHook(() => useLobbyLogic("lobby-one"));
    session.lastMessage = {
      serverMessageType: "playerUpdate",
      players: [player("another-player", "Other")],
    };

    expect(() => rerender()).not.toThrow();
    expect(session.router.replace).not.toHaveBeenCalled();
  });

  it("control: handles a player update when identity and lobby have not changed", () => {
    session.playerId = "assigned-player";
    const { result, rerender } = renderHook(() => useLobbyLogic("lobby-one"));
    session.lastMessage = {
      serverMessageType: "playerUpdate",
      players: [player("assigned-player", "Alice", true)],
    };

    rerender();

    expect(result.current.player.name).toBe("Alice");
    expect(session.router.replace).toHaveBeenCalledWith("/lobby-one/game");
  });
});
