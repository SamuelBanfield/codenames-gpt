'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

type WSStatus = 'connecting' | 'open' | 'closed';

// TODO
type Outbound = any;
// TODO
type WSMessage = any;

type SessionSnapshot = {
  players?: any[];
  game?: WSMessage;
  lobbyId?: string;
  lobbyRevision?: number;
  error?: WSMessage;
};

type WSContextType = {
  status: WSStatus;
  send: (msg: Outbound) => (() => void) | void;
  lastMessage?: WSMessage,
  session?: SessionSnapshot;
  subscribe?: (listener: (message: WSMessage) => void) => () => void;
  disconnect: () => void;
};

const WSContext = createContext<WSContextType>({
  status: 'closed',
  send: () => {},
  lastMessage: undefined,
  disconnect: () => {},
});

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WSStatus>('connecting');
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [session, setSession] = useState<SessionSnapshot>({});
  const sessionRef = useRef<SessionSnapshot>({});
  const listeners = useRef(new Set<(message: WSMessage) => void>());
  const queueRef = useRef<{ message: Outbound; cancelled: boolean }[]>([]);

  const subscribe = useCallback((listener: (message: WSMessage) => void) => {
    listeners.current.add(listener);
    return () => { listeners.current.delete(listener); };
  }, []);

  const ingest = useCallback((data: WSMessage) => {
    const previous = sessionRef.current;
    if (data.lobbyId && previous.lobbyId && data.lobbyId !== previous.lobbyId && data.serverMessageType !== 'lobbyJoined') return;
    let next = previous;
    switch (data.serverMessageType) {
      case 'lobbyJoined':
        next = { lobbyId: data.lobbyId };
        break;
      case 'lobbyLeft':
        next = {};
        break;
      case 'playerUpdate':
        if (data.lobbyRevision !== undefined && previous.lobbyRevision !== undefined && data.lobbyRevision < previous.lobbyRevision) return;
        next = { ...previous, players: data.players, lobbyRevision: data.lobbyRevision ?? previous.lobbyRevision };
        break;
      case 'stateUpdate': {
        const old = previous.game;
        if (old?.gameId && data.gameId && old.gameId !== data.gameId) return;
        if (old?.revision !== undefined && data.revision !== undefined && data.revision < old.revision) return;
        next = { ...previous, game: data, players: data.players ?? previous.players };
        break;
      }
      case 'error':
      case 'stateError':
        next = { ...previous, error: data };
        break;
    }
    // Update the authoritative snapshot for every frame, including within one
    // React batch. Navigation events are delivered once to mounted subscribers.
    sessionRef.current = next;
    setSession(next);
    setLastMessage(data);
    Array.from(listeners.current).forEach(listener => {
      if (listeners.current.has(listener)) listener(data);
    });
  }, []);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000';
    const ws = new WebSocket(`${wsUrl.replace(/\/$/, '')}/`);
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      setStatus('open');
      while (queueRef.current.length && ws.readyState === WebSocket.OPEN) {
        const queued = queueRef.current.shift();
        if (queued && !queued.cancelled) ws.send(JSON.stringify(queued.message));
      }
    };

    ws.onmessage = (ev) => {
      if (wsRef.current !== ws) return;
      try {
        const data = JSON.parse(ev.data);
        if (!data || typeof data !== 'object' || typeof data.serverMessageType !== 'string') {
          throw new Error('Invalid server message');
        }
        ingest(data);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error, ev.data);
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      setStatus('closed');
      queueRef.current = [];
    };

    ws.onerror = () => {
      if (wsRef.current !== ws) return;
      ingest({ serverMessageType: 'error', message: 'WebSocket connection failed' });
    };

    return () => {
      if (wsRef.current === ws) wsRef.current = null;
      ws.close();
    };
  }, [ingest]);

  const send = useCallback((msg: Outbound) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    } else if (ws?.readyState === WebSocket.CONNECTING || !ws) {
      queueRef.current = queueRef.current.filter(item => !item.cancelled);
      const queued = { message: msg, cancelled: false };
      queueRef.current.push(queued);
      return () => { queued.cancelled = true; };
    }
  }, []);

  const disconnect = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    ws?.close();
    queueRef.current = [];
    sessionRef.current = {};
    setSession({});
    setLastMessage(null);
    setStatus('closed');
  }, []);

  return (
    <WSContext.Provider value={{ status, send, lastMessage, session, subscribe, disconnect }}>
      {children}
    </WSContext.Provider>
  );
}

export const useWS = () => useContext(WSContext);
