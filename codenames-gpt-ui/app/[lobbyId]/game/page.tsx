"use client";

import GridComponent from "./_components/grid";
import ClueForm from "./_components/clueForm";
import OnTurnInfo from "./_components/onTurnInfo";
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
      canGuess,
      canClue,
      pending,
      error,
      canRetryAI,
      retryAI,
      status,
      leaveGame,
    } = useGameLogic();

    return (
      <main className="flex min-h-screen flex-col items-center p-12">
        <GridComponent 
          codenamesTiles={codenamesTiles} 
          guessTile={guessTile} 
          enabled={canGuess}
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
        {error && <p role="alert" className="text-red-700 m-3">{error}</p>}
        {status === 'closed' && <p role="alert">Connection lost. Reload the page to reconnect.</p>}
        {pending && <p role="status">Sending action…</p>}
        {canRetryAI && <button type="button" onClick={retryAI} disabled={pending}>Retry AI turn</button>}
        {winner && <button type="button" onClick={leaveGame} disabled={pending || status !== 'open'}>Return to lobby selection</button>}
        {canClue && (
          <ClueForm
            onSubmit={provideClue}
            disabled={pending}
          />
        )}
      </main>
    );
  }
