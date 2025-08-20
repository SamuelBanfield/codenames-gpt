"use client";

import { useEffect } from "react"

import LobbySelect from "./lobbySelect";
import { useWS } from "./wsProvider";
import { usePlayer } from "./playerIdProvider";

export default function Home() {

  const { status, send, lastMessage } = useWS();
  const { playerId, setPlayerId } = usePlayer();

  useEffect(() => {
    if (lastMessage && lastMessage.serverMessageType === "idAssign") {
      console.log("idAssign", lastMessage.uuid);
      setPlayerId(lastMessage.uuid);
      send({ clientMessageType: "lobbiesRequest" });
    }
    else {
      console.log("Unknown message type for message", lastMessage);
    }
  }, [lastMessage])

  useEffect(() => {
    send({ clientMessageType: "idRequest" });
  }, [])

  if (status === "connecting" || playerId === null) {
    return <div>Connecting...</div>;
  }

  if (status === "closed") {
    return <div>Connection failed</div>;
  }

  return (
    <LobbySelect />
  );
}

