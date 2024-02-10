"use client";

import { useState, useEffect } from "react"

const colourMap = {
  "red": "bg-red-200",
  "blue": "bg-blue-200",
  "assassin": "bg-gray-600",
  "neutral": "bg-orange-200",
  "unknown": "bg-gray-200"
}

const codeNameTile = (word: string): CodenamesTile => {
  return {
    word: word,
    team: Math.random() < 0.5 ? "red" : "blue",
    revealed: false
  };
}

const getTileColour = (tile: CodenamesTile): string => {
  return colourMap[tile.revealed ? tile.team : "unknown"];
}

export default function Home() {

  const words: string[] = [];

  const initialClue: CodenamesClue = {
    word: "fruit",
    number: 3
  };

  const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
  const [codenamesClue, setCodenamesClue] = useState<CodenamesClue>(initialClue);

  const handleMessage = (event: MessageEvent) => {
    console.log("message", event.data);
    const data = JSON.parse(event.data);
    switch (data.serverMessageType) {
      case "tilesUpdate":
        setCodenamesTiles(data.tiles);
        break;
      default:
        console.log("Unknown message type for message", data);
    }
  };

  const websocket = new WebSocket("ws://localhost:8765/");

  useEffect(() => {
    websocket.onmessage = handleMessage;
    websocket.onopen = () => {
      console.log("Connected");
      websocket.send(JSON.stringify({ clientMessageType: "tilesRequest" }));
    };

  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center p-24">
      <h1 className="text-2xl font-bold mb-4">{codenamesClue.word}, {codenamesClue.number}</h1>
      <div className="grid grid-cols-5 gap-4">
        {codenamesTiles.map((tile: CodenamesTile, index: number) => (
          <div
            key={index}
            className={`${getTileColour(tile)} p-4 text-center`}
            onClick={() => setCodenamesTiles(prev => [...prev.slice(0, index), { ...prev[index], revealed: true }, ...prev.slice(index + 1)])}
          >
            {tile.word}
          </div>
        ))}
      </div>
    </main>
  );
}

