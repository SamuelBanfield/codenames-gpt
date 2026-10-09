"use client";

import { useState } from "react"

import NameForm from "./_components/nameForm";
import { useSetNameLogic } from "./hooks/useSetNameLogic";

export default function Home({ params }: { params: { lobbyId: string } }) {
    const { nameConfirmed, confirmName, error, status } = useSetNameLogic(params.lobbyId);

    const [localName, setLocalName] = useState("");

    return (
        <main className="flex min-h-screen flex-col items-center p-24">
            <NameForm
                localName={localName}
                setLocalName={setLocalName}
                nameConfirmed={nameConfirmed}
                confirmName={confirmName}
                disabled={status !== 'open'}
            />
            {error && <p role="alert">{error}</p>}
            {status !== 'open' && <p role="status">{status === 'closed' ? 'Connection lost. Reload to reconnect.' : 'Connecting…'}</p>}
        </main>
    );
}
