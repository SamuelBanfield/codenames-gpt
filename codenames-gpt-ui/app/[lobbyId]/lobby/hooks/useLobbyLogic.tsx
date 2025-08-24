"use client"

import { usePlayer } from "@/app/playerIdProvider";
import { useCallback, useEffect, useState } from "react";
import { Player, PreferencesUpdate } from "../types";
import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/navigation";

export function useLobbyLogic(lobbyId: string) {
    const { playerId } = usePlayer();
    const [player, setCurrentPlayer] = useState<Player>({
        name: "",
        ready: false,
        role: null,
        inGame: false
    });
    const { send, lastMessage } = useWS();
    const router = useRouter();

    const handleMessage = useCallback((data: any) => {
        console.log("message", data);
        switch (data.serverMessageType) {
            case "stateError":
                console.error("Error from server:", data);
                router.push("/error");
                break;
            case "playerUpdate":
                setPlayers(data.players);
                const thisPlayer = data.players.find((p: any) => p.uuid === playerId);
                if (thisPlayer.inGame) {
                    console.log(thisPlayer);
                    router.replace(`/${lobbyId}/game`);
                }
                setCurrentPlayer(thisPlayer);
                break;
            default:
                console.log("Unknown message type while in lobby", data);
        }
    }, [router]);

    useEffect(() => {
        if (lastMessage) {
            handleMessage(lastMessage);
        }
    }, [lastMessage, handleMessage]);

    const [players, setPlayers] = useState<Player[]>([]);

    const requestPreferences = (update: PreferencesUpdate) => {
        send({ clientMessageType: "preferencesRequest", player: { ...update } });
    };

    useEffect(() => {
        requestPreferences({});
    }, []);

    return {
        player,
        players,
        requestPreferences
    };
}
