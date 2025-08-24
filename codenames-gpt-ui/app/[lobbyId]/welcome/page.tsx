"use client";

import { useEffect, useState } from "react"

import { useWS } from "../../wsProvider";
import { useRouter } from "next/navigation";
import { usePlayer } from "@/app/playerIdProvider";

export default function Home({ params }: { params: { lobbyId: string } }) {
    const { send, lastMessage } = useWS();

    const [nameConfirmed, setNameConfirmed] = useState(false);

    const router = useRouter();

    const { playerId } = usePlayer();

    const handleMessage = (data: any) => {
        console.log("message", data);
        switch (data.serverMessageType) {
            case "stateError":
                console.error("Error from server:", data);
                router.push("/error");
                break;
            case "playerUpdate":
                const thisPlayer = data.players.find((p: { uuid: string; name: string }) => p.uuid === playerId);
                if (thisPlayer && thisPlayer.name && thisPlayer.name.length > 0) {
                    setNameConfirmed(true);
                    router.push(`/${params.lobbyId}/lobby`);
                }
                break;
            default:
                console.log("Unknown message type while in lobby", data);
        }
    }

    const requestPreferences = (name: string) => {
        send({ clientMessageType: "preferencesRequest", player: { name } });
    }

    const [localName, setLocalName] = useState("");

    const confirmName = () => {
        requestPreferences(localName);
    }

    useEffect(() => {
        if (lastMessage) {
            handleMessage(lastMessage);
        }
    }, [lastMessage]);

    return (
        <main className="flex min-h-screen flex-col items-center p-24">
            <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-3">
            <label htmlFor="name" className="block text-sm font-medium mb-2">Name:</label>
            <input 
                type="text" 
                value={localName} 
                placeholder="Enter your name"
                onChange={(e) => setLocalName(e.target.value)} 
                disabled={nameConfirmed}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-2"
            />
            <button 
                onClick={confirmName} 
                disabled={localName.length < 1} 
                className={`w-full px-4 py-2 rounded-md transition-colors duration-200 font-medium ${
                localName.length < 1 
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed" 
                    : "bg-blue-500 hover:bg-blue-600 text-white"
                }`}
            >
                Enter lobby
            </button>
            </div>
        </main>
    );
}
