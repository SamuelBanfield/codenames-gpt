"use client";

import { useEffect, useState } from "react"
import GameComponent from "./_components/game_component";
import Lobby, { Player } from "./_components/lobby";

import options from "../.properties.json";

const initial = new WebSocket(`ws://${options.host}:${options.websocketPort}/`);

export default function Home() {

  const [player, setPlayer] = useState<Player>(
    {
      name: "",
      uuid: null,
      role: null,
      ready: false,
      inGame: false
    }
  );

  const [websocket, setWebsocket] = useState<WebSocket>(initial);

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
    }
    }, []
  );


  return (
    websocket.readyState === websocket.CONNECTING ? <div>Connecting...</div> :
      player.uuid && <div>
        {!player.inGame ? <Lobby websocket={websocket} player={player} setPlayer={setPlayer} />
                : <GameComponent websocket={websocket} player={player} />}
      </div>
  );
}

