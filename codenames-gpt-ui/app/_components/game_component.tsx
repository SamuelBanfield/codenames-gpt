"use client";

import { useEffect, useState } from "react";
import { Player, Role } from "./lobby";

const colourMap = {
    "red": "bg-red-200",
    "blue": "bg-blue-200",
    "assassin": "bg-gray-600",
    "neutral": "bg-yellow-100",
    "unknown": "bg-gray-200"
}

const getTileColour = (tile: CodenamesTile): string => {
  return colourMap[tile.revealed ? tile.team : "unknown"];
}

export default function GameComponent(gameProps: { websocket: WebSocket, player: Player}) {

    const { websocket, player } = gameProps;

    const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
    const [codenamesClue, setCodenamesClue] = useState<CodenamesClue | null>(null);
    
    const [localClue, setLocalClue] = useState<string | null>(null);
    const [localNumber, setLocalNumber] = useState<number | null>(null);

    const [onTurn, setOnTurn] = useState<boolean>(false);
    const [guessesRemaining, setGuessesRemaining] = useState<number | null>(null);
  
    const handleMessage = (event: MessageEvent) => {
      console.log("message", event.data);
      const data = JSON.parse(event.data);
      switch (data.serverMessageType) {
        case "stateUpdate":
          setCodenamesTiles(data.tiles);
          setCodenamesClue({word: data.clue?.word, number: data.clue?.number});
          setOnTurn(data.onTurnRole === player.role);
          if (data.guessesRemaining !== undefined) {
            setGuessesRemaining(data.guessesRemaining);
          }
          break;
        case "tilesUpdate":
          setCodenamesTiles(data.tiles);
          break;
        case "clueUpdate":
          setCodenamesClue(data.clue);
          break;
        case "onTurnUpdate":
          setOnTurn(data.onTurn);
          break;
        default:
          console.log("Unknown message type for message", data);
      }
    };
  
    const guessTile = (tile: CodenamesTile) => {
      websocket.send(JSON.stringify({ clientMessageType: "guessTile", "word": tile.word }));
    };

    const provideClue = () => {
      websocket.send(JSON.stringify({ clientMessageType: "provideClue", "word": localClue, "number": localNumber }));
      setLocalClue(null);
      setLocalNumber(null);
    };
  
    useEffect(() => {      
      websocket.onmessage = handleMessage;
      websocket.send(JSON.stringify({ clientMessageType: "initialiseRequest" }));
    }, []);
  
    return (
      <main className="flex min-h-screen flex-col items-center p-24">
        {codenamesClue?.word && <h1 className="text-2xl font-bold mb-4">{codenamesClue?.word}, {codenamesClue?.number}</h1>}
        <div className="mb-4">
          {onTurn && (player.role === Role.redSpymaster || player.role === Role.blueSpymaster) && (
            <>
              <input
                type="text"
                placeholder="Enter clue"
                value={localClue ? localClue : ""}
                onChange={(e) => setLocalClue(e.target.value)}
                className="mr-2"
              />
              <input
                type="number"
                placeholder="Enter number"
                value={localNumber ? localNumber : 0}
                onChange={(e) => e.target.valueAsNumber >= 0 ? setLocalNumber(e.target.valueAsNumber) : 0}
                className="mr-2"
              />
              <button onClick={provideClue} className={`${player.name.length < 1 ? "bg-gray-200" : "bg-blue-200 hover:bg-blue-100"} ml-2 p-1 rounded`}>Submit Clue</button>
            </>
          )}
        </div>
        <p className="mb-4">{onTurn ? "It's your turn" : "It's not your turn"}</p>
        <p className="mb-4">Guesses remaining: {guessesRemaining}</p>
        <p className="mb-4">Team: {
            ((player.role == Role.redSpymaster) || (player.role == Role.redPlayer)) ? "Red" : "Blue"
          }, {
            ((player.role == Role.redSpymaster) || (player.role == Role.blueSpymaster)) ? "You are the spymaster" : "You are guessing"
          }
        </p>
        <div className="grid grid-cols-5 gap-4">
          {codenamesTiles.map((tile: CodenamesTile, index: number) => (
            <div
              key={index}
              className={`${getTileColour(tile)} p-4 text-center rounded ${!tile.revealed? "cursor-pointer hover:margin-2 hover:shadow-md transition duration-300" : ""}`}
              onClick={() => {
                if (!tile.revealed) {
                  guessTile(tile)
                }
              }}
            >
              {tile.word}
            </div>
          ))}
        </div>
      </main>
    );
  }