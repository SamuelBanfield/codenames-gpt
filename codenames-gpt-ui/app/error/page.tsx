"use client";

import { useRouter } from 'next/navigation';


export default function GameNotFound() {
    const router = useRouter();

    return (
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 text-center">
            <h1 className="text-2xl font-bold mb-4">Error</h1>
            <p className="mb-4">An error has occurred. Did you attempt to join a game that does not exist?</p>
            <button 
            onClick={() => router.push('/')} 
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors duration-200 font-medium"
            >
            Return to Lobby selection
            </button>
        </div>
    );
}