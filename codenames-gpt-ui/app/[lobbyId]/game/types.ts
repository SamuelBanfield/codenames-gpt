
export enum Role {
    redSpymaster,
    blueSpymaster,
    redPlayer,
    bluePlayer
}

export type Player = {
    name: string;
    uuid: string | null;
    ready: boolean;
    inGame: boolean;
    inLobby: boolean;
    role: Role | null;
};