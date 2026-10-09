'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useWS } from '../wsProvider';

/** Event subscriptions never replay a previous page's navigation response. */
export function useServerMessages(handler: (message: any) => void) {
  const { subscribe, lastMessage } = useWS();
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => subscribe?.(message => handlerRef.current(message)), [subscribe]);
  // Compatibility for consumers that supply a snapshot-only context (including
  // isolated hook tests). The real provider always supplies an event subscription.
  useEffect(() => {
    if (!subscribe && lastMessage) handler(lastMessage);
  }, [subscribe, lastMessage, handler]);
}

/** Unsent commands belong to their screen and are cancelled on its unmount. */
export function useScopedSend() {
  const { send } = useWS();
  const cancellations = useRef(new Set<() => void>());
  useEffect(() => () => {
    cancellations.current.forEach(cancel => cancel());
    cancellations.current.clear();
  }, []);
  return useCallback((message: any) => {
    const cancel = send(message);
    if (cancel) cancellations.current.add(cancel);
  }, [send]);
}
