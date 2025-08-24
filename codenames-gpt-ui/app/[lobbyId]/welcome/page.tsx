"use client";

import { use, useEffect, useState } from "react"

import { useWS } from "../../wsProvider";
import { useRouter } from "next/navigation";
import { usePlayer } from "@/app/playerIdProvider";
import NameForm from "./_components/nameForm";
import { useJoinLobby } from "./hooks/useJoinLobby";

export default function Home({ params }: { params: { lobbyId: string } }) {
    const { send, lastMessage } = useWS();


    const { nameConfirmed, confirmName } = useJoinLobby(params.lobbyId);

    const [localName, setLocalName] = useState("");

    return (
        <main className="flex min-h-screen flex-col items-center p-24">
            <NameForm
                localName={localName}
                setLocalName={setLocalName}
                nameConfirmed={nameConfirmed}
                confirmName={confirmName}
            />
        </main>
    );
}
