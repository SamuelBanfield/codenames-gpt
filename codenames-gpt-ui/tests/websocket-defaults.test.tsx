import React from "react";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { WebSocketProvider } from "../app/wsProvider";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function captureWebSockets() {
  const sockets: { url: string; close: ReturnType<typeof vi.fn> }[] = [];
  class FakeWebSocket {
    constructor(url: string) { sockets.push({ url, close: this.close }); }
    close = vi.fn();
  }
  vi.stubGlobal("WebSocket", FakeWebSocket);
  return sockets;
}

it("finding 8: the default browser WebSocket URL matches the backend's default port", () => {
  // Evaluate the real Python configuration with user properties and overrides excluded.
  const backendEnvironment: NodeJS.ProcessEnv = {
    ...process.env, OPENAI_KEY: "test-key-not-a-real-credential",
  };
  for (const key of ["HOST", "WEBSOCKET_PORT", "GPT_MODEL", "GUESS_DELAY"]) {
    delete backendEnvironment[key];
  }
  const backend = spawnSync(process.env.PYTHON || "python", ["-c", [
    "from unittest.mock import patch",
    "with patch('builtins.open', side_effect=FileNotFoundError):",
    "    from codenames.options import WEBSOCKET_PORT",
    "print(WEBSOCKET_PORT)",
  ].join("\n")], {
    cwd: resolve(process.cwd(), "../backend"),
    env: backendEnvironment,
    encoding: "utf8",
    timeout: 10_000,
  });
  expect(backend.error).toBeUndefined();
  expect(backend.status, backend.stderr).toBe(0);
  const port = Number(backend.stdout.trim());
  expect(Number.isInteger(port) && port > 0).toBe(true);

  const sockets = captureWebSockets();
  vi.stubEnv("NEXT_PUBLIC_WEBSOCKET_URL", "");

  render(<WebSocketProvider><div>Test client</div></WebSocketProvider>);

  expect(sockets).toHaveLength(1);
  expect(new URL(sockets[0].url).port).toBe(String(port));
});

it("control: an explicitly configured WebSocket URL is used and closed on unmount", () => {
  const sockets = captureWebSockets();
  vi.stubEnv("NEXT_PUBLIC_WEBSOCKET_URL", "ws://localhost:9001");

  const { unmount } = render(<WebSocketProvider><div>Test client</div></WebSocketProvider>);

  expect(sockets).toHaveLength(1);
  expect(sockets[0].url).toBe("ws://localhost:9001/");
  unmount();
  expect(sockets[0].close).toHaveBeenCalledOnce();
});
