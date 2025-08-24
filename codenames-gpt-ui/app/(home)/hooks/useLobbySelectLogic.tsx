"use client"

import { usePlayer } from "@/app/playerIdProvider";
import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Lobby } from "../types";

export function useLobbySelectLogic() {
  
    const { status, send, lastMessage } = useWS();
    const { setPlayerId } = usePlayer();
    const router = useRouter();
    
    const [lobbies, setLobbies] = useState<Lobby[]>([]);
  
    useEffect(() => {
      send({ clientMessageType: "idRequest" });
    }, [])
  
    const createNewLobby = (name: string) => {
      send({ clientMessageType: "createLobby", name });
    };
  
    const refreshLobbies = () => {
      send({ clientMessageType: "lobbiesRequest" });
    }
  
    const handleMessage = useCallback((data: any) => {
      switch (data.serverMessageType) {
        case "error":
          console.error("Error from server:", data);
          refreshLobbies();
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
          console.log("lobbyJoined", data.lobbyId);
          router.replace(`/${data.lobbyId}/welcome`);
          break;
        default:
          console.log("Unknown message type while in lobby select", data);
      }
    }, [refreshLobbies, router, send, setLobbies, setPlayerId]);

    useEffect(() => {
      if (lastMessage) {
        handleMessage(lastMessage);
      }
    }, [lastMessage, handleMessage]);
  
    const joinLobby = (lobbyId: string) => {
      send({ clientMessageType: "joinLobby", lobbyId });
    }

    return {
      status,
      lobbies,
      createNewLobby,
      refreshLobbies,
      joinLobby
    };
  
}
