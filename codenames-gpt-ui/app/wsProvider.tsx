'use client';

import React, { createContext, useContext, useEffect, useRef, useState } from 'react';

import options from "../.properties.json";

type WSStatus = 'connecting' | 'open' | 'closed';

// TODO
type Outbound = any;
// TODO
type WSMessage = any;

type WSContextType = {
  status: WSStatus;
  send: (msg: Outbound) => void;
  lastMessage?: WSMessage
};

const WSContext = createContext<WSContextType>({
  status: 'closed',
  send: () => {},
  lastMessage: undefined,
});

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WSStatus>('connecting');
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  const queueRef = useRef<Outbound[]>([]);

  useEffect(() => {
    let closedByApp = false;

    const connect = () => {
      const ws = new WebSocket(`ws://${options.host}:${options.websocketPort}/`);
      wsRef.current = ws;
      setStatus('connecting');

      ws.onopen = () => {
        setStatus('open');

        while (queueRef.current.length && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(queueRef.current.shift()));
        }
      };

      ws.onmessage = (ev) => {
        const data = JSON.parse(ev.data);
        setLastMessage(data);
      };

      ws.onclose = () => {
        setStatus('closed');
        if (!closedByApp) {
          // TODO: handle reconnection?
        }
      };

      ws.onerror = () => {
      };
    };

    connect();

    return () => {
      closedByApp = true;
      wsRef.current?.close();
    };
  }, []);

  const send = (msg: Outbound) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    } else {
      queueRef.current.push(msg);
    }
  };
  return (
    <WSContext.Provider value={{ status, send, lastMessage }}>
      {children}
    </WSContext.Provider>
  );
}

export const useWS = () => useContext(WSContext);
