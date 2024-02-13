"use client";

import { useEffect, useState } from "react"
import GameComponent from "./_components/game_component";
import Lobby, { Player } from "./_components/lobby";

const websocket = new WebSocket("ws://localhost:8765/");
websocket.onopen = () => {
  console.log("Connected");
};

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
    websocket.send(JSON.stringify({ clientMessageType: "idRequest" }));
  }, []);


  return (
    <main>
      {player.uuid && <div>
        {!player.inGame ? <Lobby websocket={websocket} player={player} setPlayer={setPlayer} />
                : <GameComponent websocket={websocket} player={player} />}
      </div>}
    </main>
  );
}

