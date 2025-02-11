"use client";

import { useEffect, useState } from "react";
import { Player, Role } from "./lobby";

const notRevealedColourMap = {
  "red": "bg-red-200",
  "blue": "bg-blue-200",
  "assassin": "bg-gray-400",
  "neutral": "bg-yellow-100",
  "unknown": "bg-gray-200"
}

const revealedColourMap = {
  "red": "bg-red-500",
  "blue": "bg-blue-500",
  "assassin": "bg-gray-800",
  "neutral": "bg-yellow-500",
  "unknown": "bg-gray-200"
}

const roleTurnToDisplayMap = {
  0: "The Red spymaster is thinking of a clue",
  1: "The Blue spymaster is thinking of a clue",
  2: "The Red team are guessing",
  3: "The Blue team are guessing"
}

const getTileColour = (tile: CodenamesTile): string => {
  return tile.revealed === true
    ? revealedColourMap[tile.team]
    : notRevealedColourMap[tile.team];
}

export default function GameComponent(gameProps: { websocket: WebSocket, player: Player}) {

    const { websocket, player } = gameProps;

    const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
    const [codenamesClue, setCodenamesClue] = useState<CodenamesClue | null>(null);
    
    const [localClue, setLocalClue] = useState<string | null>(null);
    const [localNumber, setLocalNumber] = useState<number | null>(null);

    const [onTurnRole, setOnTurnRole] = useState<Role | null>(null);
    const [guessesRemaining, setGuessesRemaining] = useState<number | null>(null);

    const [winner, setWinner] = useState<string | null>(null);
  
    const handleMessage = (event: MessageEvent) => {
      console.log("message", event.data);
      const data = JSON.parse(event.data);
      switch (data.serverMessageType) {
        case "stateUpdate":
          setCodenamesTiles(data.tiles);
          setCodenamesClue({word: data.clue?.word, number: data.clue?.number});
          setOnTurnRole(data.onTurnRole);
          if (data.guessesRemaining !== undefined) {
            setGuessesRemaining(data.guessesRemaining);
          }
          if (data.winner !== undefined) {
            setWinner(data.winner);
          }
          break;
        case "tilesUpdate":
          setCodenamesTiles(data.tiles);
          break;
        case "clueUpdate":
          setCodenamesClue(data.clue);
          break;
        default:
          console.log("Unknown message type while in game", data);
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

    const explanatoryText = (role: Role | null) => {
      if (role === null) {
        return "";
      }
      if (role === Role.redSpymaster || role === Role.blueSpymaster) {
        return "It's your turn, enter a word that links to as many of your team's words as possible, without linking to the other team's words or the assassin. Then, enter the number of words that your clue links to and press submit";
      }
      return "It's your turn, click on the word that links to the clue to guess";
    }
  
    useEffect(() => {      
      websocket.onmessage = handleMessage;
      websocket.send(JSON.stringify({ clientMessageType: "initialiseRequest" }));
    }, []);
  
    return (
      <main className="flex min-h-screen flex-col items-center p-12">
        <h1 className="text-2xl font-bold py-4">Codenames GPT</h1>
          <div className="grid grid-cols-5 gap-4">
          {codenamesTiles.map((tile: CodenamesTile, index: number) => (
            <div
              key={index}
              className={`${tile.team === "assassin" ? "text-white" : "text-black"} ${getTileColour(tile)} p-4 text-center rounded ${!tile.revealed? "cursor-pointer hover:margin-2 hover:shadow-md transition duration-300" : ""}`}
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
        <div className="flex flex-col items-center h-50">
          {winner === null && <div className="flex flex-col items-center">
            {codenamesClue?.word && <h1 className="text-2xl font-bold m-2">{codenamesClue?.word}, {codenamesClue?.number}</h1>}
            <p className="m-2">{
              player.role === onTurnRole 
                ? explanatoryText(player.role)
                : (onTurnRole ? roleTurnToDisplayMap[onTurnRole] : "")}
                </p>
            {(onTurnRole === Role.bluePlayer || onTurnRole === Role.redPlayer) && <p className="mb-4">Guesses remaining: {guessesRemaining}</p>}
            <p className="m-2">
                You are on team {((player.role == Role.redSpymaster) || (player.role == Role.redPlayer)) ? "Red" : "Blue"}
            </p>
          </div>
          }
          {(winner !== null) && <h1 className="m-2">Game over, the {winner} team has won!</h1>
          }
        </div>
        <div className="m-2">
          {player.role === onTurnRole && (player.role === Role.redSpymaster || player.role === Role.blueSpymaster) && (
            <>
              <input
                type="text"
                className="border p-1 rounded m-1"  
                placeholder="Enter clue"
                value={localClue ? localClue : ""}
                onChange={(e) => setLocalClue(e.target.value)}
              />
              <input
                type="number"
                placeholder="Enter number"
                value={localNumber ? localNumber : 0}
                onChange={(e) => e.target.valueAsNumber >= 0 ? setLocalNumber(e.target.valueAsNumber) : 0}
                className="border p-1 m-1 w-20"
              />
              <button onClick={provideClue} className={`${player.name.length < 1 ? "bg-gray-200" : "bg-blue-200 hover:bg-blue-100"} m-1 p-1 rounded`}>Submit Clue</button>
            </>
          )}
        </div>
      </main>
    );
  }