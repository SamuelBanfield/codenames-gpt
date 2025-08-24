"use client";

import RoleGrid from "./_components/roleGrid";
import ReadyBox from "./_components/readyBox";
import { useLobbyLogic } from "./hooks/useLobbyLogic";

export default function RoleSelect({ params }: { params: { lobbyId: string } }) {

    const { player, players, requestPreferences } = useLobbyLogic(params.lobbyId);

    return (
        <main className="p-24">
            <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
                <RoleGrid players={players} requestPreferences={requestPreferences} player={player} />
                <ReadyBox player={player} requestPreferences={requestPreferences} />
            </div>
        </main>
    );
}