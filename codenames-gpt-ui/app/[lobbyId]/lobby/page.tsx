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
            case "stateError":
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
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
            <div className="grid grid-cols-2 gap-3 mb-6">
            <div className={`${playerWithRole(Role.redSpymaster)? "bg-red-100" : "bg-red-500 hover:bg-red-600 cursor-pointer"} p-4 text-center rounded-md transition-colors duration-200`} onClick={() => requestPreferences({...player, role: Role.redSpymaster})}>
            <div className={`font-medium ${playerWithRole(Role.redSpymaster) ? "text-red-800" : "text-white"}`}>Red Spymaster</div>
            <div className={`text-sm h-6 ${playerWithRole(Role.redSpymaster) ? "text-red-600" : "text-red-100"}`}><i>{playerWithRole(Role.redSpymaster)?.name}</i></div>
            </div>
            <div className={`${playerWithRole(Role.blueSpymaster)? "bg-blue-100" : "bg-blue-500 hover:bg-blue-600 cursor-pointer"} p-4 text-center rounded-md transition-colors duration-200`} onClick={() => requestPreferences({...player, role: Role.blueSpymaster})}>
            <div className={`font-medium ${playerWithRole(Role.blueSpymaster) ? "text-blue-800" : "text-white"}`}>Blue Spymaster</div>
            <div className={`text-sm h-6 ${playerWithRole(Role.blueSpymaster) ? "text-blue-600" : "text-blue-100"}`}><i>{playerWithRole(Role.blueSpymaster)?.name}</i></div>
            </div>
            <div className={`${playerWithRole(Role.redPlayer)? "bg-red-100" : "bg-red-500 hover:bg-red-600 cursor-pointer"} p-4 text-center rounded-md transition-colors duration-200`} onClick={() => requestPreferences({...player, role: Role.redPlayer})}>
            <div className={`font-medium ${playerWithRole(Role.redPlayer) ? "text-red-800" : "text-white"}`}>Red Player</div>
            <div className={`text-sm h-6 ${playerWithRole(Role.redPlayer) ? "text-red-600" : "text-red-100"}`}><i>{playerWithRole(Role.redPlayer)?.name}</i></div>
            </div>
            <div className={`${playerWithRole(Role.bluePlayer)? "bg-blue-100" : "bg-blue-500 hover:bg-blue-600 cursor-pointer"} p-4 text-center rounded-md transition-colors duration-200`} onClick={() => requestPreferences({...player, role: Role.bluePlayer})}>
            <div className={`font-medium ${playerWithRole(Role.bluePlayer) ? "text-blue-800" : "text-white"}`}>Blue Player</div>
            <div className={`text-sm h-6 ${playerWithRole(Role.bluePlayer) ? "text-blue-600" : "text-blue-100"}`}><i>{playerWithRole(Role.bluePlayer)?.name}</i></div>
            </div>
            </div>
            <div className="flex items-center justify-center">
            <label htmlFor="ready" className="mr-3 font-medium">Ready: </label>
            <input
            type="checkbox"
            checked={player.ready}
            onChange={(e) => requestPreferences({ ready: e.target.checked })}
            className="h-5 w-5 text-blue-500 focus:ring-2 focus:ring-blue-500 rounded"
            disabled={player.role === null}
            />
            </div>
        </div>
    );
}