"use client"

import { useCallback } from "react";

type NameFormProps = {
    localName: string;
    setLocalName: (name: string) => void;
    nameConfirmed: boolean;
    confirmName: (name: string) => void;
}

export default function NameForm({ localName, setLocalName, nameConfirmed, confirmName }: NameFormProps) {

    const handleConfirmName = useCallback((name: string) => {
        confirmName(name);
    }, [confirmName, localName]);

    return (
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
                    onClick={() => confirmName(localName)} 
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
    )
}