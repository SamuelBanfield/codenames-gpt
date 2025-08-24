export enum Role {
    redSpymaster,
    blueSpymaster,
    redPlayer,
    bluePlayer
}

export type Player = {
    name: string;
    ready: boolean
    role: Role | null;
    inGame: boolean;
}

export type PreferencesUpdate = {
    ready?: boolean;
    role?: Role | null;
}