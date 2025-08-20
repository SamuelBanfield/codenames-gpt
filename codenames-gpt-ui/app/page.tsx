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
        router.push(`/${data.lobbyId}/welcome`);
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
    <div>
      <div className="flex flex-col items-center">
        <h1 className="text-2xl font-bold py-2">Codenames GPT</h1>
        <p>Select one of the open lobbies below, or enter a name and click create to start your own</p>
        <div className="flex mt-auto py-8">
          <input 
            type="text" 
            placeholder="Lobby name" 
            className="border p-1 rounded" 
            value={lobbyName} 
            onChange={(e) => setLobbyName(e.target.value)} 
              />
          <button 
            className={`${lobbyName.length < 1 ? "bg-gray-200" : "bg-blue-200 hover:bg-blue-100"} ml-2 p-1 rounded"`}
            onClick={() => createNewLobby(lobbyName)}
            disabled={lobbyName.length < 1}
              >
                Create New Lobby
            </button>
          <button 
            className="bg-blue-200 hover:bg-blue-100 ml-2 p-1 rounded" 
            onClick={refreshLobbies}
              >
              Refresh lobbies
          </button>
        </div>
      </div>
      <table className="table-auto w-full mt-4">
        <thead>
          <tr>
        <th className="px-4 py-2">Lobby Name</th>
        <th className="px-4 py-2">Players</th>
        <th className="px-4 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {lobbies.map((lobby) => (
        <tr 
          className={`cursor-pointer ${lobbyStatus(lobby) === "Open" ? "hover:bg-gray-100" : "bg-gray-300"}`}
          onClick={() => joinLobby(lobby.id)} 
          key={lobby.id}
        >
          <td className="border border-black px-4 py-2">{lobby.name}</td>
          <td className="border border-black px-4 py-2">{lobby.players}/4</td>
          <td className="border border-black px-4 py-2">{lobbyStatus(lobby)}</td>
        </tr>
          ))}
          {Array.from({ length: Math.max(0, 10 - lobbies.length) }).map((_, index) => (
        <tr key={`empty-${index}`}>
          <td className="border border-black px-4 py-2">&nbsp;</td>
          <td className="border border-black px-4 py-2">&nbsp;</td>
          <td className="border border-black px-4 py-2">&nbsp;</td>
        </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

