"use client"

import { useCallback } from "react";
import { Player, PreferencesUpdate, Role } from "../types";

type RoleGridProps = {
    players: Player[];
    requestPreferences: (prefs: PreferencesUpdate) => void;
    player: Player;
}

export default function RoleGrid({ players, requestPreferences, player }: RoleGridProps) {

    const playerWithRole = useCallback((role: Role) => {
        return players.find(p => p.role === role);
    }, [players]);

    return (
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
    );
}