"use client";

import { UUID } from "crypto";
import { useEffect, useState } from "react";

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
    role: Role | null;
};

export default function Lobby(lobbyProps: { websocket: WebSocket, player: Player, setPlayer: any }) {
        
    const {websocket, player, setPlayer} = lobbyProps;
    const [nameConfirmed, setNameConfirmed] = useState(false);

    const handleMessage = (event: MessageEvent) => {
        console.log("message", event.data);
        const data = JSON.parse(event.data);
        switch (data.serverMessageType) {
            case "playerUpdate":
                setPlayers(data.players);
                const thisPlayer = data.players.find((p: Player) => p.uuid === player.uuid);
                if (thisPlayer.name && thisPlayer.name.length > 0) {
                    setNameConfirmed(true);
                }
                setPlayer(data.players.find((p: Player) => p.uuid === player.uuid));
                break;
            default:
                console.log("Unknown message type for message", data);
        }
    }

    const [players, setPlayers] = useState<Player[]>([player]);

    const requestPreferences = (player: Player) => {
        websocket.send(JSON.stringify({clientMessageType: "preferencesRequest", player}));
    }

    const [localName, setLocalName] = useState("");

    const confirmName = () => {
        requestPreferences({ ...player, name: localName });
    }

    useEffect(() => {
        websocket.onmessage = handleMessage;
    }, []);

    const playerWithRole = (role: Role) => {
        return players.find(p => p.role === role);
    }

    return (
        <main className="flex min-h-screen flex-col items-center p-24">
            <div className="mb-4">
                <label htmlFor="name">Name: </label>
                <input type="text" value={localName} onChange={(e) => setLocalName(e.target.value)} disabled={nameConfirmed} />
                {!nameConfirmed && <button onClick={confirmName} disabled={localName.length < 2} className={`${player.name.length < 1 ? "bg-gray-200" : "bg-blue-200 hover:bg-blue-100"} ml-2 p-1 rounded`}>
                    Confirm
                </button>}
            </div>
            {nameConfirmed && 
            <div className="grid grid-cols-2 gap-4 mb-4">
                <div className={`${playerWithRole(Role.redSpymaster)? "bg-red-100" : "bg-red-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 flex justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.redSpymaster})}>
                    Red Spymaster
                    {playerWithRole(Role.redSpymaster) && <span className="text-xs">{playerWithRole(Role.redSpymaster)?.name}</span>}
                </div>
                <div className={`${playerWithRole(Role.blueSpymaster)? "bg-blue-100" : "bg-blue-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 flex justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.blueSpymaster})}>
                    Blue Spymaster
                    {playerWithRole(Role.blueSpymaster) && <span className="text-xs">{playerWithRole(Role.blueSpymaster)?.name}</span>}
                </div>
                <div className={`${playerWithRole(Role.redPlayer)? "bg-red-100" : "bg-red-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 flex justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.redPlayer})}>
                    Red Player
                    {playerWithRole(Role.redPlayer) && <span className="text-xs">{playerWithRole(Role.redPlayer)?.name}</span>}
                </div>
                <div className={`${playerWithRole(Role.bluePlayer)? "bg-blue-100" : "bg-blue-300 cursor-pointer hover:margin-2 hover:shadow-md transition duration-300"} p-6 flex justify-center rounded`} onClick={() => requestPreferences({...player, role: Role.bluePlayer})}>
                    Blue Player
                    {playerWithRole(Role.bluePlayer) && <span className="text-xs">{playerWithRole(Role.bluePlayer)?.name}</span>}
                </div>
            </div>}
            {nameConfirmed && <div className="flex items-center">
                <label htmlFor="ready" className="mr-2">Ready: </label>
                <input
                    type="checkbox"
                    checked={player.ready}
                    onChange={(e) => requestPreferences({ ...player, ready: e.target.checked })}
                    className="form-checkbox h-5 w-5 text-blue-500"
                    disabled={player.role === null}
                />
            </div>}
        </main>
    );
}