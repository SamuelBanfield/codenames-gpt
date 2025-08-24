"use client";

import { useEffect, useState } from "react";
import { useWS } from "../../wsProvider";
import { usePlayer } from "@/app/playerIdProvider";
import { useRouter } from "next/navigation";

export enum Role {
    redSpymaster,
    blueSpymaster,
    redPlayer,
    bluePlayer
}

export type Player = {
    name: string;
    uuid: string | null;
    ready: boolean;
    inGame: boolean;
    inLobby: boolean;
    role: Role | null;
};

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

export default function GameComponent() {

    const { playerId } = usePlayer();
    const [player, setPlayer] = useState<Player | null>(null);

    const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
    const [codenamesClue, setCodenamesClue] = useState<CodenamesClue | null>(null);
    
    const [localClue, setLocalClue] = useState<string | null>(null);
    const [localNumber, setLocalNumber] = useState<number | null>(null);

    const [onTurnRole, setOnTurnRole] = useState<Role | null>(null);
    const [guessesRemaining, setGuessesRemaining] = useState<number | null>(null);

    const [winner, setWinner] = useState<string | null>(null);

    const { send, lastMessage } = useWS();
    const router = useRouter();

    const handleMessage = (data: any) => {
      switch (data.serverMessageType) {
        case "error":
          console.error("Error from server:", data);
          router.push("/error");
          break;
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
        case "playerUpdate":
          const thisPlayer = data.players.find((p: any) => p.uuid === playerId);
          if (thisPlayer) {
            setPlayer(thisPlayer);
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
      send({ clientMessageType: "guessTile", "word": tile.word });
    };

    const provideClue = () => {
      send({ clientMessageType: "provideClue", "word": localClue, "number": localNumber });
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

    const getTurnText = () => {
      return player?.role === onTurnRole 
          ? explanatoryText(player.role)
          : (onTurnRole ? roleTurnToDisplayMap[onTurnRole] : "")
    }

    useEffect(() => {
      if (lastMessage) {
        handleMessage(lastMessage);
      }
    }, [lastMessage])

    useEffect(() => {
      send({ clientMessageType: "initialiseRequest", includeUserInfo: true });
    }, []);
  
    return (
      <main className="flex min-h-screen flex-col items-center p-12">
        <div className="grid grid-cols-5 gap-4">
          {codenamesTiles.map((tile: CodenamesTile, index: number) => (
        <div
          key={index}
          className={`${tile.team === "assassin" ? "text-white" : "text-black"} ${getTileColour(tile)} p-4 text-center rounded-md ${!tile.revealed? "cursor-pointer hover:shadow-lg transition-all duration-200" : ""}`}
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
        {getTurnText() && <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 m-2 max-w-lg text-center">
          <p className="text-lg text-blue-800 font-medium">
            {getTurnText()}
          </p>
        </div>}
        {(onTurnRole === Role.bluePlayer || onTurnRole === Role.redPlayer) && 
          <p className="mb-4 text-lg font-semibold text-gray-700">Guesses remaining: {guessesRemaining}</p>
        }
        <div className={`px-4 py-2 rounded-full font-semibold text-white m-2 ${
          ((player?.role == Role.redSpymaster) || (player?.role == Role.redPlayer)) 
            ? "bg-red-500" 
            : "bg-blue-500"
        }`}>
          You are on team {((player?.role == Role.redSpymaster) || (player?.role == Role.redPlayer)) ? "Red" : "Blue"}
        </div>
          </div>
          }
          {(winner !== null) && 
        <div className="text-center m-2">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Game Over. Team {winner.charAt(0).toUpperCase() + winner.slice(1)} Wins!</h1>
        </div>
          }
        </div>
        {player?.role === onTurnRole && (player?.role === Role.redSpymaster || player?.role === Role.blueSpymaster) && (
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-3">
          <input
            type="text"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-2"
            placeholder="Enter clue"
            value={localClue ? localClue : ""}
            onChange={(e) => setLocalClue(e.target.value)}
          />
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="Enter number"
              value={localNumber ? localNumber : 0}
              onChange={(e) => e.target.valueAsNumber >= 0 ? setLocalNumber(e.target.valueAsNumber) : 0}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button 
              onClick={provideClue} 
              className="flex-shrink-0 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors duration-200 font-medium"
            >
              Submit Clue
            </button>
          </div>
        </div>
          )}
      </main>
    );
  }