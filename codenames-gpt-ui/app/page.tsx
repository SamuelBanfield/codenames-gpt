"use client";

import { useEffect, useState } from "react"
import GameComponent from "./_components/gameComponent";
import Lobby, { Player } from "./_components/lobby";

import options from "../.properties.json";
import LobbySelect from "./_components/lobbySelect";

const initial = new WebSocket(`ws://${options.host}:${options.websocketPort}/`);

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

  const [websocket, setWebsocket] = useState<WebSocket>(initial);
  const [connectionFailed, setConnectionFailed] = useState(false);

  const handleIdMessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data);
    if (data.serverMessageType === "idAssign") {
      console.log("idAssign", data.uuid);
      setPlayer({ ...player, uuid: data.uuid });
    }
    else {
      console.log("Unknown message type for message", data);
    }
  }

  useEffect(() => {
    websocket.onmessage = handleIdMessage
    if (websocket.readyState === websocket.OPEN) {
      websocket.send(JSON.stringify({ clientMessageType: "idRequest" }));
    }
    else {
      websocket.onopen = () => websocket.send(JSON.stringify({ clientMessageType: "idRequest" }));
      websocket.onerror = (event) => {
        console.error("Connection failed", event);
        setConnectionFailed(true);
      }
    }
    }, []
  );

  console.log("player", player);

  if (websocket.readyState === websocket.CONNECTING || player.uuid === null) {
    return <div>Connecting...</div>;
  }

  if (connectionFailed) {
    return <div>Connection failed</div>;
  }
  
  if (player.inGame) {
    return <GameComponent websocket={websocket} player={player} />;
  }

  if (player.inLobby) {
    return <Lobby websocket={websocket} player={player} setPlayer={setPlayer} />;
  }

  return (
    <LobbySelect websocket={websocket} player={player} setPlayer={setPlayer} />
  );
}

