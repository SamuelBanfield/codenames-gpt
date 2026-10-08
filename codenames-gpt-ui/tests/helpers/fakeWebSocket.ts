import { vi } from "vitest";

export type ClientMessage = { clientMessageType: string; [key: string]: unknown };

/** Frames and socket lifecycle events are delivered explicitly by each test. */
export class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  send = vi.fn<(data: string) => void>();
  close = vi.fn(() => { this.readyState = FakeWebSocket.CLOSED; });

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  receive(message: unknown) {
    this.onmessage?.(new MessageEvent<string>("message", { data: JSON.stringify(message) }));
  }

  disconnect() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  messages(): ClientMessage[] {
    return this.send.mock.calls.map(([data]) => JSON.parse(data));
  }
}
