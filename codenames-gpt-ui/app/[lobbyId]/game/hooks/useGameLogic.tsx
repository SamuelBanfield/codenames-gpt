"use client";

import { useWS } from "@/app/wsProvider";
import { useScopedSend, useServerMessages } from "@/app/hooks/useServerMessages";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Player, Role } from "../types";
import { usePlayer } from "@/app/playerIdProvider";

export function useThings() {
  const { playerId } = usePlayer();
  const { status, session } = useWS();
  const send = useScopedSend();
  const router = useRouter();
  const [player, setPlayer] = useState<Player | null>(null);
  const [state, setState] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);

  const handleMessage = useCallback((data: any) => {
    if (data.serverMessageType === "stateError") {
      router.replace("/error");
    } else if (data.serverMessageType === "lobbyLeft") {
      setState(null);
      setPlayer(null);
      router.replace("/");
    } else if (data.serverMessageType === "error") {
      setError(data.message);
      pendingRef.current = false;
      setPending(false);
    } else if (data.serverMessageType === "stateUpdate") {
      setState(data);
      setPlayer(data.players?.find((p: Player) => p.uuid === playerId) ?? null);
      pendingRef.current = false;
      setPending(false);
    } else if (data.serverMessageType === "playerUpdate") {
      setPlayer(data.players?.find((p: Player) => p.uuid === playerId) ?? null);
    }
  }, [playerId, router]);

  useServerMessages(handleMessage);
  useEffect(() => {
    if (session?.game) handleMessage(session.game);
    else if (session?.players) handleMessage({ serverMessageType: "playerUpdate", players: session.players });
  }, [session?.game, session?.players, handleMessage]);
  useEffect(() => {
    send({ clientMessageType: "initialiseRequest", includeUserInfo: true });
  }, [send]);

  const winner = state?.winner ?? null;
  const onTurnRole = state?.onTurnRole ?? null;
  const active = status === "open" && !winner && (!state?.phase || state.phase === "active");
  const onTurn = active && player?.role !== null && player?.role === onTurnRole;
  const canGuess = !!onTurn && (player?.role === Role.redPlayer || player?.role === Role.bluePlayer);
  const canClue = !!onTurn && (player?.role === Role.redSpymaster || player?.role === Role.blueSpymaster);

  const command = useCallback((message: any) => {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setError(null);
    send({ ...message, gameId: state?.gameId, turnId: state?.turnId });
  }, [send, state?.gameId, state?.turnId]);

  const guessTile = useCallback((tile: CodenamesTile) => {
    if (canGuess && !tile.revealed) command({ clientMessageType: "guessTile", word: tile.word });
  }, [canGuess, command]);

  const provideClue = useCallback((word: string | null, number: number | null) => {
    if (!canClue) return;
    if (!word?.trim() || !Number.isInteger(number) || !number || number < 1 || number > 25) {
      setError("Enter a clue and a whole-number count between 1 and 25.");
      return;
    }
    command({ clientMessageType: "provideClue", word: word.trim(), number });
  }, [canClue, command]);

  const retryAI = useCallback(() => {
    if (active && state?.aiError) command({ clientMessageType: "retryAI" });
  }, [active, state?.aiError, command]);
  const leaveGame = useCallback(() => {
    if (status === 'open') command({ clientMessageType: "leaveLobby" });
  }, [status, command]);

  return {
    codenamesTiles: (state?.tiles ?? []) as CodenamesTile[],
    codenamesClue: state?.clue ?? null,
    guessesRemaining: state?.guessesRemaining ?? null,
    onTurnRole, player, winner, guessTile, provideClue,
    canGuess: canGuess && !pending, canClue, pending,
    error: error ?? state?.aiError ?? null,
    canRetryAI: active && !!state?.aiError, retryAI, status,
    leaveGame,
  };
}
