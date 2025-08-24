"use client"

const notRevealedColourMap = {
  "red": "bg-red-200",
  "blue": "bg-blue-200",
  "assassin": "bg-gray-400",
  "neutral": "bg-yellow-100",
  "unknown": "bg-gray-200"
}

const revealedColourMap = {
  "red": "bg-red-500",
  "blue": "bg-blue-500",
  "assassin": "bg-gray-800",
  "neutral": "bg-yellow-500",
  "unknown": "bg-gray-200"
}

const getTileColour = (tile: CodenamesTile): string => {
  return tile.revealed === true
    ? revealedColourMap[tile.team]
    : notRevealedColourMap[tile.team];
}

export type GridProps = {
    codenamesTiles: CodenamesTile[];
    guessTile: (tile: CodenamesTile) => void;
};

export default function GridComponent({ codenamesTiles, guessTile }: GridProps) {
    return (
        <div className="grid grid-cols-5 gap-4">
            {codenamesTiles.map((tile: CodenamesTile, index: number) => (
                <div
                    key={index}
                    className={`${tile.team === "assassin" ? "text-white" : "text-black"} ${getTileColour(tile)} p-4 text-center rounded-md ${!tile.revealed? "cursor-pointer hover:shadow-lg transition-all duration-200" : ""}`}
                    onClick={() => {
                        if (!tile.revealed) {
                            guessTile(tile)
                        }
                    }}
                >
                    {tile.word}
                </div>
            ))}
        </div>
    );
}
