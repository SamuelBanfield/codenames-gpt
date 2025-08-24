"use client";

import { useState } from "react"

import NameForm from "./_components/nameForm";
import { useSetNameLogic } from "./hooks/useSetNameLogic";

export default function Home({ params }: { params: { lobbyId: string } }) {
    const { nameConfirmed, confirmName } = useSetNameLogic(params.lobbyId);

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
