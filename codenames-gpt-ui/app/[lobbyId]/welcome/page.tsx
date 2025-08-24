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
            case "error":
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
            <h1 className="text-2xl font-bold py-2">Codenames GPT</h1>
            <div className="mb-4 py-5">
                <label htmlFor="name">Name: </label>
                <input className="border p-1 rounded" type="text" value={localName} onChange={(e) => setLocalName(e.target.value)} disabled={nameConfirmed} />
                <button onClick={confirmName} disabled={localName.length < 1} className={`${localName.length < 1 ? "bg-gray-200" : "bg-blue-200 hover:bg-blue-100"} ml-2 p-1 rounded`}>
                    Enter lobby
                </button>
            </div>
        </main>
    );
}
