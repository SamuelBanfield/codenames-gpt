"use client";

import { useEffect, useState } from "react"
import GameComponent from "./_components/gameComponent";
import Lobby, { Player } from "./_components/lobby";

import LobbySelect from "./_components/lobbySelect";
import { useWS } from "./wsProvider";
import { stat } from "fs";

export default function Home() {

  const [player, setPlayer] = useState<Player>(
    {
      name: "",
      uuid: null,
      role: null,
      ready: false,
      inGame: false,
      inLobby: false
    }
  );

  const { status, send, lastMessage } = useWS();

  const handleIdMessage = (data: any) => {
    if (data.serverMessageType === "idAssign") {
      console.log("idAssign", data.uuid);
      setPlayer({ ...player, uuid: data.uuid });
      send({ clientMessageType: "lobbiesRequest" });
    }
    else {
      console.log("Unknown message type for message", data);
    }
  }

  useEffect(() => {
    if (lastMessage && lastMessage.serverMessageType === "idAssign") {
      console.log("idAssign", lastMessage.uuid);
      setPlayer({ ...player, uuid: lastMessage.uuid });
      send({ clientMessageType: "lobbiesRequest" });
    }
    else {
      console.log("Unknown message type for message", lastMessage);
    }
  }, [lastMessage])

  useEffect(() => {
    send({ clientMessageType: "idRequest" });
  }, [])

  console.log("player", player);

  if (status === "connecting" || player.uuid === null) {
    return <div>Connecting...</div>;
  }

  if (status === "closed") {
    return <div>Connection failed</div>;
  }
  
  if (player.inGame) {
    return <GameComponent player={player} />;
  }

  if (player.inLobby) {
    return <Lobby player={player} setPlayer={setPlayer} />;
  }

  return (
    <LobbySelect player={player} setPlayer={setPlayer} />
  );
}

