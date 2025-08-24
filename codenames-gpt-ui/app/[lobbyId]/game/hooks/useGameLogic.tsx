"use client"

import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/dist/client/components/navigation";
import { useCallback, useEffect, useState } from "react";
import { Player, Role } from "../types";
import { usePlayer } from "@/app/playerIdProvider";

export function useThings() {
    
    const { playerId } = usePlayer();
    const [player, setPlayer] = useState<Player | null>(null);

    const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>([]);
    const [codenamesClue, setCodenamesClue] = useState<CodenamesClue | null>(null);

    const [onTurnRole, setOnTurnRole] = useState<Role | null>(null);
    const [guessesRemaining, setGuessesRemaining] = useState<number | null>(null);

    const [winner, setWinner] = useState<string | null>(null);

    const { send, lastMessage } = useWS();
    const router = useRouter();

    const handleMessage = useCallback((data: any) => {
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
    }, [playerId, router]);
    
    useEffect(() => {
      if (lastMessage) {
        handleMessage(lastMessage);
      }
    }, [lastMessage, handleMessage]);

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
      send({ clientMessageType: "initialiseRequest", includeUserInfo: true });
    }, []);

    return {
        codenamesTiles,
        guessTile,
        provideClue,
        onTurnRole,
        guessesRemaining,
        player,
        winner,
        codenamesClue,
    };
}