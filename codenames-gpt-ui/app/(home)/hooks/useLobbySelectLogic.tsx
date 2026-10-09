"use client"

import { usePlayer } from "@/app/playerIdProvider";
import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Lobby } from "../types";
import { useScopedSend, useServerMessages } from "@/app/hooks/useServerMessages";

export function useLobbySelectLogic() {
  
    const { status } = useWS();
    const send = useScopedSend();
    const { setPlayerId } = usePlayer();
    const router = useRouter();
    
    const [lobbies, setLobbies] = useState<Lobby[]>([]);
    const [pending, setPending] = useState(false);
    const pendingRef = useRef(false);
    const [error, setError] = useState<string | null>(null);
  
    useEffect(() => {
      send({ clientMessageType: "idRequest" });
    }, [send])
  
    const createNewLobby = (name: string) => {
      if (status !== 'open' || pendingRef.current || !name.trim()) return;
      pendingRef.current = true;
      setPending(true);
      setError(null);
      send({ clientMessageType: "createLobby", name: name.trim() });
    };
  
    const refreshLobbies = useCallback(() => {
      send({ clientMessageType: "lobbiesRequest" });
    }, [send]);
  
    const handleMessage = useCallback((data: any) => {
      switch (data.serverMessageType) {
        case "error":
          setError(data.message);
          pendingRef.current = false;
          setPending(false);
          break;
        case "idAssign":
          console.log("idAssign", data.uuid);
          setPlayerId(data.uuid);
          refreshLobbies();
          break;
        case "lobbiesUpdate":
          console.log("lobbiesUpdate", data.lobbies);
          setLobbies(data.lobbies);
          break;
        case "lobbyJoined":
          pendingRef.current = false;
          setPending(false);
          console.log("lobbyJoined", data.lobbyId);
          router.replace(`/${data.lobbyId}/welcome`);
          break;
        default:
          console.log("Unknown message type while in lobby select", data);
      }
    }, [refreshLobbies, router, setPlayerId]);

    useServerMessages(handleMessage);
  
    const joinLobby = (lobbyId: string) => {
      if (status !== 'open' || pendingRef.current) return;
      pendingRef.current = true;
      setPending(true);
      setError(null);
      send({ clientMessageType: "joinLobby", lobbyId });
    }

    return {
      status,
      lobbies,
      createNewLobby,
      refreshLobbies,
      joinLobby,
      pending,
      error,
    };
  
}
