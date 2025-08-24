"use client"

import { Lobby } from "../types"


const lobbyStatus = (lobby: Lobby) => {
  if (lobby.game) {
    return "Game in progress";
  }
  return lobby.players >= 4 ? "Full" : "Open";
}

type LobbyTableProps = {
    lobbies: Lobby[]
    joinLobby: (lobbyId: string) => void
}

export default function LobbyTable({ lobbies, joinLobby }: LobbyTableProps) {
    return (
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
    )
}