"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useWS } from "../../../wsProvider";
import { usePlayer } from "@/app/playerIdProvider";
import { useScopedSend, useServerMessages } from "@/app/hooks/useServerMessages";

export function useSetNameLogic(lobbyId: string) {
  const { session, status } = useWS();
  const send = useScopedSend();
  const { playerId } = usePlayer();
  const router = useRouter();

  const [nameConfirmed, setNameConfirmed] = useState(false);

  const handleMessage = useCallback((data: any) => {
    switch (data.serverMessageType) {
      case "stateError":
        console.error("Error from server:", data);
        router.replace("/error");
        break;
      case "playerUpdate": {
        const thisPlayer = data.players.find((p: { uuid: string; name?: string }) => p.uuid === playerId);
        if (thisPlayer?.name && thisPlayer.name.length > 0) {
          setNameConfirmed(true);
          router.replace(`/${lobbyId}/${thisPlayer.inGame ? 'game' : 'lobby'}`);
        }
        break;
      }
      default:
        console.warn("Unknown message type on welcome page", data);
    }
  }, [playerId, router, lobbyId]);

  useServerMessages(handleMessage);
  useEffect(() => {
    if (session?.players) handleMessage({ serverMessageType: 'playerUpdate', players: session.players });
  }, [session?.players, handleMessage]);

  const confirmName = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed || status !== 'open' || session?.game) return;
    send({ clientMessageType: "preferencesRequest", player: { name: trimmed } });
  }, [send, status, session?.game]);

  return { nameConfirmed, confirmName, error: session?.error?.message, status };
}
