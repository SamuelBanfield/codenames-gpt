"use client";

import { usePlayer } from "@/app/playerIdProvider";
import { useWS } from "@/app/wsProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Player, PreferencesUpdate } from "./types";
import RoleGrid from "./_components/roleGrid";
import ReadyBox from "./_components/readyBox";

export default function RoleSelect({ params }: { params: { lobbyId: string } }) {

    const { playerId } = usePlayer();
    const [player, setCurrentPlayer] = useState<Player>({
        name: "",
        ready: false,
        role: null,
        inGame: false
    });
    const { send, lastMessage } = useWS();
    const router = useRouter();

    const handleMessage = (data: any) => {
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
                    router.replace(`/${params.lobbyId}/game`);
                }
                setCurrentPlayer(thisPlayer);
                break;
            default:
                console.log("Unknown message type while in lobby", data);
        }
    }

    const [players, setPlayers] = useState<Player[]>([]);

    const requestPreferences = (update: PreferencesUpdate) => {
        send({ clientMessageType: "preferencesRequest", player: { ...update } });
    };

    useEffect(() => {
        requestPreferences({});
    }, []);

    useEffect(() => {
        if (lastMessage) {
            handleMessage(lastMessage);
        }
    }, [lastMessage]);

    return (
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
            <RoleGrid players={players} requestPreferences={requestPreferences} player={player} />
            <ReadyBox player={player} requestPreferences={requestPreferences} />
        </div>
    );
}