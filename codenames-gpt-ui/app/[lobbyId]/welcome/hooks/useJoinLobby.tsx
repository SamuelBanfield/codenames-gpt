"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useWS } from "../../../wsProvider";
import { usePlayer } from "@/app/playerIdProvider";

export function useJoinLobby(lobbyId: string) {
  const { send, lastMessage } = useWS();
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
          router.replace(`/${lobbyId}/lobby`);
        }
        break;
      }
      default:
        console.warn("Unknown message type on welcome page", data);
    }
  }, [playerId, router, lobbyId]);

  useEffect(() => {
    if (lastMessage) {
        handleMessage(lastMessage);
    }
  }, [lastMessage, handleMessage]);

  const confirmName = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    send({ clientMessageType: "preferencesRequest", player: { name: trimmed } });
  }, [send]);

  return { nameConfirmed, confirmName };
}