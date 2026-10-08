import React, { StrictMode } from "react";
import { act, fireEvent, render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WebSocketProvider, useWS } from "../app/wsProvider";
import HomePage from "../app/(home)/page";
import LobbyPage from "../app/[lobbyId]/lobby/page";
import { useLobbyLogic } from "../app/[lobbyId]/lobby/hooks/useLobbyLogic";
import { useThings as useGameLogic } from "../app/[lobbyId]/game/hooks/useGameLogic";
import GamePage from "../app/[lobbyId]/game/page";
import { FakeWebSocket } from "./helpers/fakeWebSocket";

// Transport, page components, and hooks are real; only identity and navigation
// are supplied externally, like their providers in a running application.
const session = vi.hoisted(() => ({
  playerId: "player-one",
  setPlayerId: vi.fn(),
  router: { push: vi.fn(), replace: vi.fn() },
}));
vi.mock("@/app/playerIdProvider", () => ({ usePlayer: () => session }));
vi.mock("next/navigation", () => ({ useRouter: () => session.router }));
vi.mock("next/dist/client/components/navigation", () => ({ useRouter: () => session.router }));

function Wrapper({ children }: { children: React.ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

function StrictWrapper({ children }: { children: React.ReactNode }) {
  return <StrictMode><Wrapper>{children}</Wrapper></StrictMode>;
}

function currentSocket() {
  const socket = FakeWebSocket.instances.at(-1);
  if (!socket) throw new Error("The real provider did not construct a socket");
  return socket;
}

function roster(role = 2, inGame = true) {
  return {
    serverMessageType: "playerUpdate",
    players: [{ uuid: "player-one", name: "Human", role, ready: true, inGame, inLobby: true }],
  };
}

function snapshot({ role = 2, onTurnRole = 2, winner = null as string | null } = {}) {
  return {
    serverMessageType: "stateUpdate",
    players: roster(role).players,
    tiles: [{ word: "UNREVEALED", team: "unknown", revealed: false }],
    clue: { word: "CLUE", number: 2 },
    guessesRemaining: 1,
    onTurnRole,
    winner,
    new_turn: true,
  };
}

function LobbyScreen() {
  useLobbyLogic("room");
  return <div>Lobby</div>;
}

describe("endgame and route timing reproductions", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubEnv("NEXT_PUBLIC_WEBSOCKET_URL", "ws://test.invalid");
    vi.clearAllMocks();
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("retains player identity when roster and game state arrive before one render", () => {
    const { result } = renderHook(useGameLogic, { wrapper: Wrapper });
    const socket = currentSocket();
    act(() => socket.open());

    // One controlled render batch reproduces two frames arriving before React
    // has consumed the first. This does not assert that every network pair batches.
    act(() => {
      socket.receive(roster(0));
      socket.receive(snapshot({ role: 0, onTurnRole: 0 }));
    });

    expect(result.current.codenamesTiles).toHaveLength(1);
    expect(result.current.player?.uuid).toBe("player-one");
  });

  it("navigates from lobby when its started roster is followed immediately by game state", () => {
    renderHook(() => useLobbyLogic("room"), { wrapper: Wrapper });
    const socket = currentSocket();
    act(() => socket.open());

    act(() => {
      socket.receive(roster());
      socket.receive(snapshot());
    });

    expect(session.router.replace).toHaveBeenCalledWith("/room/game");
  });

  it("uses the roster in a full snapshot even without a separate player update", () => {
    const { result } = renderHook(useGameLogic, { wrapper: Wrapper });
    const socket = currentSocket();
    act(() => socket.open());

    act(() => socket.receive(snapshot({ role: 0, onTurnRole: 0 })));

    expect(result.current.player?.role).toBe(0);
  });

  it("does not send a pregame preferences mutation after a retained roster directs it into the game", () => {
    const view = render(<Wrapper><div>Transitioning</div></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive(roster()));
    socket.send.mockClear();

    view.rerender(<Wrapper><LobbyScreen /></Wrapper>);

    expect(session.router.replace).toHaveBeenCalledWith("/room/game");
    expect(socket.messages().filter(message => message.clientMessageType === "preferencesRequest"))
      .toHaveLength(0);
  });

  it("does not replay an already handled lobbyJoined response when returning to home", () => {
    const view = render(<Wrapper><HomePage /></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive({ serverMessageType: "lobbyJoined", lobbyId: "room" }));
    expect(session.router.replace).toHaveBeenCalledWith("/room/welcome");
    view.rerender(<Wrapper><div>Welcome</div></Wrapper>);
    session.router.replace.mockClear();

    view.rerender(<Wrapper><HomePage /></Wrapper>);

    expect(session.router.replace).not.toHaveBeenCalled();
  });

  it("does not flush queued role preferences after the lobby screen unmounts", () => {
    const view = render(<Wrapper><LobbyPage params={{ lobbyId: "room" }} /></Wrapper>);
    const socket = currentSocket();
    // Unlike home, the real lobby page exposes controls while connecting.
    fireEvent.click(view.getByText("Red Spymaster"));
    expect(socket.send).not.toHaveBeenCalled();
    view.rerender(<Wrapper><div>Another route</div></Wrapper>);

    act(() => socket.open());

    const roleChanges = socket.messages().filter(message =>
      message.clientMessageType === "preferencesRequest" &&
      (message.player as { role?: number } | undefined)?.role === 0,
    );
    expect(roleChanges).toHaveLength(0);
  });

  it("does not duplicate mutation-shaped lobby initialization during Strict Mode replay", () => {
    renderHook(() => useLobbyLogic("room"), { wrapper: StrictWrapper });
    const socket = currentSocket();

    act(() => socket.open());

    const mutations = socket.messages().filter(message => message.clientMessageType === "preferencesRequest");
    expect(mutations.length).toBeLessThanOrEqual(1);
  });

  it("ignores a replaced socket's delayed close event", () => {
    const { result } = renderHook(useWS, { wrapper: StrictWrapper });
    const old = FakeWebSocket.instances[0];
    const current = currentSocket();
    expect(current).not.toBe(old);
    act(() => current.open());
    expect(result.current.status).toBe("open");

    act(() => old.disconnect());

    expect(current.readyState).toBe(FakeWebSocket.OPEN);
    expect(result.current.status).toBe("open");
  });

  it("ignores a replaced socket's late state frame", () => {
    const { result } = renderHook(useWS, { wrapper: StrictWrapper });
    const old = FakeWebSocket.instances[0];
    const current = currentSocket();
    act(() => {
      current.open();
      current.receive({ serverMessageType: "stateUpdate", marker: "current" });
    });

    act(() => old.receive({ serverMessageType: "stateUpdate", marker: "obsolete" }));

    expect(result.current.lastMessage.marker).toBe("current");
  });

  it.each([
    { scenario: "after victory", winner: "red", onTurnRole: 2 },
    { scenario: "off turn", winner: null, onTurnRole: 1 },
  ])("does not emit tile guesses $scenario", ({ winner, onTurnRole }) => {
    const view = render(<Wrapper><GamePage /></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive(roster()));
    act(() => socket.receive(snapshot({ winner, onTurnRole })));
    socket.send.mockClear();

    fireEvent.click(view.getByText("UNREVEALED"));

    expect(socket.messages().filter(message => message.clientMessageType === "guessTile"))
      .toHaveLength(0);
  });

  it("removes or disables clue submission when the winner is known", () => {
    const view = render(<Wrapper><GamePage /></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive(roster(1)));
    act(() => socket.receive(snapshot({ role: 1, onTurnRole: 1, winner: "red" })));

    const submit = view.queryByRole("button", { name: "Submit Clue" });
    expect(submit === null || (submit instanceof HTMLButtonElement && submit.disabled)).toBe(true);
  });

  it("displays a rejected action's server error instead of silently logging it", () => {
    const view = render(<Wrapper><GamePage /></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive(roster(0)));
    act(() => socket.receive(snapshot({ role: 0, onTurnRole: 0 })));

    act(() => socket.receive({ serverMessageType: "error", message: "Clue rejected" }));

    expect(view.queryByText(/Clue rejected/)).not.toBeNull();
  });

  it("control: consumes separately committed roster and game messages", () => {
    const { result } = renderHook(useGameLogic, { wrapper: Wrapper });
    const socket = currentSocket();
    act(() => socket.open());
    act(() => socket.receive(roster(0)));
    act(() => socket.receive(snapshot({ role: 0, onTurnRole: 0 })));

    expect(result.current.player?.uuid).toBe("player-one");
    expect(result.current.player?.role).toBe(0);
    expect(result.current.codenamesTiles).toHaveLength(1);
  });

  it("control: delivers role preferences from the currently mounted connected lobby", () => {
    const view = render(<Wrapper><LobbyPage params={{ lobbyId: "room" }} /></Wrapper>);
    const socket = currentSocket();
    act(() => socket.open());
    socket.send.mockClear();

    fireEvent.click(view.getByText("Red Spymaster"));

    expect(socket.messages()).toHaveLength(1);
    expect(socket.messages()[0]).toMatchObject({
      clientMessageType: "preferencesRequest", player: { role: 0 },
    });
  });
});
