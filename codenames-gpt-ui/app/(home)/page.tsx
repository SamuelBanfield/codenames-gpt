"use client";

import { usePlayer } from "../playerIdProvider";
import CreateLobbyForm from "./_components/createLobbyForm";
import LobbyTable from "./_components/lobbyTable";
import { useLobbySelectLogic } from "./hooks/useLobbySelectLogic";

export default function Home() {

  const { playerId } = usePlayer();

  const { status, lobbies, createNewLobby, refreshLobbies, joinLobby } = useLobbySelectLogic();

  if (status === "connecting" || playerId === null) {
    return <div>Connecting...</div>;
  }

  if (status === "closed") {
    return <div>Connection failed</div>;
  }

  return (
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-6">
      <div className="flex flex-col items-center">
        <p className="text-gray-600 mb-6">Select one of the open lobbies below, or enter a name and click create to start your own</p>
        <CreateLobbyForm createNewLobby={createNewLobby} refreshLobbies={refreshLobbies} />
      </div>
      <LobbyTable lobbies={lobbies} joinLobby={joinLobby} />
    </div>
  );
}
