"use client";

import { useEffect, useState } from "react"

import { useWS } from "./wsProvider";
import { usePlayer } from "./playerIdProvider";
import { useRouter } from "next/navigation";

interface Lobby {
  id: string;
  name: string;
  players: number;
  game: boolean;
}

const lobbyStatus = (lobby: Lobby) => {
  if (lobby.game) {
    return "Game in progress";
  }
  return lobby.players >= 4 ? "Full" : "Open";
}

export default function Home() {
  
  const { status, send, lastMessage } = useWS();
  const { playerId, setPlayerId } = usePlayer();
  
  const [lobbies, setLobbies] = useState<Lobby[]>([]);
  const [lobbyName, setLobbyName] = useState("");

  const router = useRouter();

  useEffect(() => {
    send({ clientMessageType: "idRequest" });
  }, [])

  const createNewLobby = (name: string) => {
    send({ clientMessageType: "createLobby", name });
  };

  const refreshLobbies = () => {
    send({ clientMessageType: "lobbiesRequest" });
  }

  useEffect(() => {
    if (lastMessage) {
      handleMessage(lastMessage);
    }
  }, [lastMessage]);

  const handleMessage = (data: any) => {
    switch (data.serverMessageType) {
      case "error":
        console.error("Error from server:", data);
        refreshLobbies();
        break;
      case "idAssign":
        console.log("idAssign", data.uuid);
        setPlayerId(data.uuid);
        refreshLobbies();
        break;
      case "lobbiesUpdate":
        console.log("lobbiesUpdate", data.lobbies);
        setLobbies(data.lobbies);
        break;
      case "lobbyJoined":
        console.log("lobbyJoined", data.lobbyId);
        router.replace(`/${data.lobbyId}/welcome`);
        break;
      default:
        console.log("Unknown message type while in lobby select", data);
    }
  }

  const joinLobby = (lobbyId: string) => {
    send({ clientMessageType: "joinLobby", lobbyId });
  }

  
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
      <div className="flex gap-2 mb-6 w-full max-w-md">
        <input 
        type="text" 
        placeholder="Lobby name" 
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
        value={lobbyName} 
        onChange={(e) => setLobbyName(e.target.value)} 
        />
        <button 
        className={`px-4 py-2 rounded-md transition-colors duration-200 font-medium ${
          lobbyName.length < 1 
          ? "bg-gray-300 text-gray-500 cursor-not-allowed" 
          : "bg-blue-500 hover:bg-blue-600 text-white"
        }`}
        onClick={() => createNewLobby(lobbyName)}
        disabled={lobbyName.length < 1}
        >
        Create
        </button>
        <button 
        className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors duration-200 font-medium" 
        onClick={refreshLobbies}
        >
        Refresh
        </button>
      </div>
      </div>
      <table className="table-auto w-full border border-gray-300 rounded-md overflow-hidden">
      <thead>
        <tr className="bg-gray-50">
        <th className="px-4 py-3 text-left font-medium text-gray-700 border-b border-gray-300">Lobby Name</th>
        <th className="px-4 py-3 text-left font-medium text-gray-700 border-b border-gray-300">Players</th>
        <th className="px-4 py-3 text-left font-medium text-gray-700 border-b border-gray-300">Status</th>
        </tr>
      </thead>
      <tbody>
        {lobbies.map((lobby) => (
        <tr 
          className={`cursor-pointer transition-colors duration-200 ${
          lobbyStatus(lobby) === "Open" 
            ? "hover:bg-blue-50" 
            : "bg-gray-100 cursor-not-allowed"
          }`}
          onClick={() => lobbyStatus(lobby) === "Open" && joinLobby(lobby.id)} 
          key={lobby.id}
        >
          <td className="border-b border-gray-200 px-4 py-3">{lobby.name}</td>
          <td className="border-b border-gray-200 px-4 py-3">{lobby.players}/4</td>
          <td className="border-b border-gray-200 px-4 py-3">{lobbyStatus(lobby)}</td>
        </tr>
        ))}
        {Array.from({ length: Math.max(0, 10 - lobbies.length) }).map((_, index) => (
        <tr key={`empty-${index}`}>
          <td className="border-b border-gray-200 px-4 py-3">&nbsp;</td>
          <td className="border-b border-gray-200 px-4 py-3">&nbsp;</td>
          <td className="border-b border-gray-200 px-4 py-3">&nbsp;</td>
        </tr>
        ))}
      </tbody>
      </table>
    </div>
  );
}

