"use client";

import { useCallback, useEffect, useState } from "react";
import { useWS } from "../../wsProvider";
import { usePlayer } from "@/app/playerIdProvider";
import { useRouter } from "next/navigation";
import GridComponent from "./_components/grid";
import ClueForm from "./_components/clueForm";
import OnTurnInfo from "./_components/onTurnInfo";

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

export default function GameComponent() {

    const { playerId } = usePlayer();
    const [player, setPlayer] = useState<Player | null>(null);

    const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
    const [codenamesClue, setCodenamesClue] = useState<CodenamesClue | null>(null);

    const [onTurnRole, setOnTurnRole] = useState<Role | null>(null);
    const [guessesRemaining, setGuessesRemaining] = useState<number | null>(null);

    const [winner, setWinner] = useState<string | null>(null);

    const { send, lastMessage } = useWS();
    const router = useRouter();

    const handleMessage = (data: any) => {
      switch (data.serverMessageType) {
        case "stateError":
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
  
    const guessTile = useCallback((tile: CodenamesTile) => {
      send({ clientMessageType: "guessTile", "word": tile.word });
    }, [send]);

    const provideClue = useCallback((clue: string | null, number: number | null) => {
      if (clue?.trim() && number) {
        send({ clientMessageType: "provideClue", "word": clue, "number": number });
      }
      else {
        console.error("Invalid clue or number: ", { clue, number });
      }
    }, [send]);

    useEffect(() => {
      if (lastMessage) {
        handleMessage(lastMessage);
      }
    }, [lastMessage])

    useEffect(() => {
      send({ clientMessageType: "initialiseRequest", includeUserInfo: true });
    }, [send]);
  
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