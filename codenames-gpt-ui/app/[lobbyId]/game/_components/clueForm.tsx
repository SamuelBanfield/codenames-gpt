"use client"

import { useState } from "react";

export type ClueFormProps = {
    onSubmit: (clue: string | null, number: number | null) => void;
};

export default function ClueForm({onSubmit }: ClueFormProps) {
      
  const [localClue, setLocalClue] = useState<string>("");
  const [localNumber, setLocalNumber] = useState<number>(0);

  const handleSubmit = () => {
    onSubmit(localClue, localNumber);
  };

  return (
    <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-3">
      <input
        type="text"
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-2"
        placeholder="Enter clue"
        value={localClue ? localClue : ""}
        onChange={(e) => setLocalClue(e.target.value)}
      />
      <div className="flex gap-2">
        <input
          type="number"
          placeholder="Enter number"
          value={localNumber ? localNumber : 0}
          onChange={(e) => setLocalNumber(e.target.valueAsNumber >= 0 ? e.target.valueAsNumber : 0)}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button 
          onClick={handleSubmit}
          className="flex-shrink-0 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors duration-200 font-medium"
        >
          Submit Clue
        </button>
      </div>
    </div>
    )
}