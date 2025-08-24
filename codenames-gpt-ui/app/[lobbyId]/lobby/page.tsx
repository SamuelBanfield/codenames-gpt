"use client";

import { usePlayer } from "@/app/playerIdProvider";
import { useWS } from "@/app/wsProvider";
import { read } from "fs";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export enum Role {
    redSpymaster,
    blueSpymaster,
    redPlayer,
    bluePlayer
}

export type Player = {
    name: string;
    ready: boolean
    role: Role | null;
    inGame: boolean;
}

export type PreferencesUpdate = {
    ready?: boolean;
    role?: Role | null;
}

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
            case "error":
                console.error("Error from server:", data);
                router.push("/error");
                break;
            case "playerUpdate":
                setPlayers(data.players);
                const thisPlayer = data.players.find((p: any) => p.uuid === playerId);
                if (thisPlayer.inGame) {
                    console.log(thisPlayer);
                    router.push(`/${params.lobbyId}/game`);
                }
                setCurrentPlayer({
                    ...player,
                    ready: thisPlayer?.ready ?? false,
                    role: thisPlayer?.role ?? null
                });
                break;
            default:
                console.log("Unknown message type while in lobby", data);
        }
    }

    const [players, setPlayers] = useState<Player[]>([]);

    const requestPreferences = (update: PreferencesUpdate) => {
        send({ clientMessageType: "preferencesRequest", player: { ...update } });
    }

    useEffect(() => {
        requestPreferences({});
    }, []);

    useEffect(() => {
        if (lastMessage) {
            handleMessage(lastMessage);
        }
    }, [lastMessage]);

    const playerWithRole = (role: Role) => {
        return players.find(p => p.role === role);
    }

    return (
        <main className="flex min-h-screen flex-col items-center p-24">
            <h1 className="text-2xl font-bold py-2">Codenames GPT</h1>
            <div className="grid grid-cols-2 gap-4 mb-4">
                <div className={`${playerWithRole(Role.redSpymaster)? "bg-red-100" : "bg-red-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.redSpymaster})}>
                    <div>Red Spymaster</div>
                    <div className="text-s h-6"><i>{playerWithRole(Role.redSpymaster)?.name}</i></div>
                </div>
                <div className={`${playerWithRole(Role.blueSpymaster)? "bg-blue-100" : "bg-blue-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.blueSpymaster})}>
                    <div>Blue Spymaster</div>
                    <div className="text-s h-6"><i>{playerWithRole(Role.blueSpymaster)?.name}</i></div>
                </div>
                <div className={`${playerWithRole(Role.redPlayer)? "bg-red-100" : "bg-red-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.redPlayer})}>
                    <div>Red Player</div>
                    <div className="text-s h-6"><i>{playerWithRole(Role.redPlayer)?.name}</i></div>
                </div>
                <div className={`${playerWithRole(Role.bluePlayer)? "bg-blue-100" : "bg-blue-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.bluePlayer})}>
                    Blue Player
                    <div className="text-s h-6"><i>{playerWithRole(Role.bluePlayer)?.name}</i></div>
                </div>
            </div>
            <div className="flex items-center">
                <label htmlFor="ready" className="mr-2">Ready: </label>
                <input
                    type="checkbox"
                    checked={player.ready}
                    onChange={(e) => requestPreferences({ ready: e.target.checked })}
                    className="form-checkbox h-5 w-5 text-blue-500"
                    disabled={player.role === null}
                />
            </div>
        </main>
    );
}