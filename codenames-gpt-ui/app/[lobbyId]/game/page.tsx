"use client";

import GridComponent from "./_components/grid";
import ClueForm from "./_components/clueForm";
import OnTurnInfo from "./_components/onTurnInfo";
import { Role } from "./types";
import { useThings as useGameLogic } from "./hooks/useGameLogic";

export default function GameComponent() {
    const {
      codenamesTiles,
      guessTile,
      provideClue,
      onTurnRole,
      guessesRemaining,
      player,
      winner,
      codenamesClue,
    } = useGameLogic();

    return (
      <main className="flex min-h-screen flex-col items-center p-12">
        <GridComponent 
          codenamesTiles={codenamesTiles} 
          guessTile={guessTile} 
        />
        <div className="flex flex-col items-center h-50">
          <OnTurnInfo 
            winner={winner}
            codenamesClue={codenamesClue ?? {word: null, number: null}} 
            onTurnRole={onTurnRole} 
            guessesRemaining={guessesRemaining} 
            player={player} 
          />
        </div>
        {player?.role === onTurnRole && (player?.role === Role.redSpymaster || player?.role === Role.blueSpymaster) && (
          <ClueForm
            onSubmit={provideClue}
          />
        )}
      </main>
    );
  }