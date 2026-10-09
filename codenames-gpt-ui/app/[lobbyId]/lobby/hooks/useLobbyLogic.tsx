"use client"

import { usePlayer } from "@/app/playerIdProvider";
import { useCallback, useEffect, useState } from "react";
import { Player, PreferencesUpdate } from "../types";
import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/navigation";
import { useScopedSend, useServerMessages } from "@/app/hooks/useServerMessages";

export function useLobbyLogic(lobbyId: string) {
    const { playerId } = usePlayer();
    const [player, setCurrentPlayer] = useState<Player>({
        name: "",
        ready: false,
        role: null,
        inGame: false
    });
    const { session, status } = useWS();
    const send = useScopedSend();
    const router = useRouter();

    const handleMessage = useCallback((data: any) => {
        switch (data.serverMessageType) {
            case "stateError":
                console.error("Error from server:", data);
                router.replace("/error");
                break;
            case "playerUpdate":
            case "stateUpdate":
                if (!Array.isArray(data.players)) break;
                setPlayers(data.players);
                const thisPlayer = data.players.find((p: any) => p.uuid === playerId);
                if (!thisPlayer) break;
                if (thisPlayer.inGame) {
                    router.replace(`/${lobbyId}/game`);
                }
                setCurrentPlayer(thisPlayer);
                break;
            default:
                console.log("Unknown message type while in lobby", data);
        }
    }, [router, playerId, lobbyId]);

    useServerMessages(handleMessage);
    useEffect(() => {
        if (session?.players) handleMessage({ serverMessageType: "playerUpdate", players: session.players });
    }, [session?.players, handleMessage]);

    const [players, setPlayers] = useState<Player[]>([]);

    const requestPreferences = useCallback((update: PreferencesUpdate) => {
        if (status !== 'open' || player.inGame || session?.game) return;
        send({ clientMessageType: "preferencesRequest", player: { ...update } });
    }, [send, status, player.inGame, session?.game]);

    useEffect(() => {
        send({ clientMessageType: "initialiseRequest", includeUserInfo: true });
    }, [send]);

    return {
        player,
        players,
        requestPreferences,
        error: session?.error?.message,
        status,
    };
}
