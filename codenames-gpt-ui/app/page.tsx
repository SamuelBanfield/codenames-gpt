"use client";

import Image from 'next/image'
import { useState } from 'react';

const colourMap = {
  "red": "red-200",
  "blue": "blue-200",
  "assassin": "gray-600",
  "neutral": "orange-200",
  "unknown": "gray-200"
}

const codeNameTile = (word: string): CodenamesTile => {
  return {
    word: word,
    team: Math.random() < 0.5 ? "red" : "blue",
    revealed: false
  };
}

const getTileColour = (tile: CodenamesTile): string => {
  if (tile.revealed) {
    return colourMap[tile.team];
  } else {
    return colourMap["unknown"];
  }
}

export default function Home() {

  const words: string[] = [
    "apple", "banana", "carrot", "dog", "elephant",
    "fox", "grape", "horse", "ice cream", "jellyfish",
    "kiwi", "lemon", "mango", "nut", "orange",
    "pear", "quail", "rabbit", "strawberry", "turtle",
    "unicorn", "violet", "watermelon", "xylophone", "zebra"
  ];

  const initial: CodenamesTile[] = words.map((word: string) => codeNameTile(word));

  const [codenamesTiles, setCodenamesTiles] = useState<CodenamesTile[]>(initial);

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className="grid grid-cols-5 gap-4">
        {codenamesTiles.map((tile: CodenamesTile, index: number) => (
          <div
            key={index}
            className={`bg-${getTileColour(tile)} p-4 text-center`}
            onClick={() => setCodenamesTiles(prev => [...prev.slice(0, index), { ...prev[index], revealed: true }, ...prev.slice(index + 1)])}
          >
            {tile.word}
          </div>
        ))}
      </div>
    </main>
  )
}
