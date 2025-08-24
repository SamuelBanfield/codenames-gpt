"use client"

import { useState } from "react";

type CreateLobbyFormProps = {
    createNewLobby: (name: string) => void;
    refreshLobbies: () => void;
}

export default function CreateLobbyForm({ createNewLobby, refreshLobbies }: CreateLobbyFormProps) {

    const [lobbyName, setLobbyName] = useState("");

    return (
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
    )
}