"use client";

import { useRouter } from 'next/navigation';


export default function GameNotFound() {
    const router = useRouter();

    return (
        <div className="p-8 text-center">
            <h1 className="text-2xl font-bold mb-4">Error</h1>
            <p>An error has occurred. Did you attempt to join a game that does not exist?</p>
            <button 
                onClick={() => router.push('/')} 
                className="mt-4 inline-block text-blue-600 underline"
            >
                Return to Lobby selection
            </button>
        </div>
    );
}