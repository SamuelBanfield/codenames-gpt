type CodenamesTile = {
    word: string;
    revealed: boolean;
    team: "unknown" | "red" | "blue" | "neutral" | "assassin";
};

type CodenamesClue = {
    word: string;
    number: number;
};
