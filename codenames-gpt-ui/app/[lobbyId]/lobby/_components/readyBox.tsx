"use client"

import { Player, PreferencesUpdate } from "../types";

type ReadyBoxProps = {
    player: Player;
    requestPreferences: (prefs: PreferencesUpdate) => void;
}

export default function ReadyBox({ player, requestPreferences }: ReadyBoxProps) {
    return (
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
    )
}