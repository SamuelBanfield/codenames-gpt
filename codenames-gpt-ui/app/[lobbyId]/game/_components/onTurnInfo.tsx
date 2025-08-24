"use client"

import { Player, Role } from "../types";

export type OnTurnInfoProps = {
    winner: string | null;
    codenamesClue: { word: string | null; number: number | null };
    onTurnRole: Role | null;
    guessesRemaining: number | null;
    player: Player | null;
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

const roleTurnToDisplayMap = {
  0: "The Red spymaster is thinking of a clue",
  1: "The Blue spymaster is thinking of a clue",
  2: "The Red team are guessing",
  3: "The Blue team are guessing"
}

export default function OnTurnInfo({ winner, codenamesClue, onTurnRole, guessesRemaining, player }: OnTurnInfoProps) {
    
    const getTurnText = () => {
        return player?.role === onTurnRole 
            ? explanatoryText(player.role)
            : (onTurnRole !== null ? roleTurnToDisplayMap[onTurnRole] : "")
    }
    
    
    if (winner !== null) {
        return (
            <div className="text-center m-2">
                <h1 className="text-2xl font-bold text-gray-800 mb-2">Game Over. Team {winner.charAt(0).toUpperCase() + winner.slice(1)} Wins!</h1>
            </div>
        );
    }
    
    return (
        <>
            <div className="flex flex-col items-center">
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
        </>
    )
}