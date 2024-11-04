import { useEffect, useState } from "react";
import { Player } from "./lobby";

interface Lobby {
  id: string;
  // name: string;
}

type LobbySelectProps = {
  websocket: WebSocket;
  player: Player;
  setPlayer: (player: Player) => void;
}

export default function LobbySelect(props: LobbySelectProps) {

  const { websocket, player, setPlayer } = props;
  const [lobbies, setLobbies] = useState<Lobby[]>([]);

  const createNewLobby = () => {
    websocket.send(JSON.stringify({ clientMessageType: "createLobby" }));
  };

  const refreshLobbies = () => {
    websocket.send(JSON.stringify({ clientMessageType: "lobbiesRequest" }));
  }

  websocket.onmessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data);
    switch (data.serverMessageType) {
      case "lobbiesUpdate":
        setLobbies(data.lobbies.map((lobbyId: string) => ({ id: lobbyId })));
        break;
      case "lobbyJoined":
        console.log("lobbyJoined", data.lobbyId);
        setPlayer({ ...player, inLobby: true });
        break;
      default:
        console.log("Unknown message type while in lobby select", data);
    }
  }

  const joinLobby = (lobbyId: string) => {
    websocket.send(JSON.stringify({clientMessageType: "joinLobby", lobbyId}));
  }

  return (
    <div>
      <h1>Lobby Select</h1>
      <button className="bg-blue-200 hover:bg-blue-100 ml-2 p-1 rounded" onClick={createNewLobby}>Create New Lobby</button>
      <button className="bg-blue-200 hover:bg-blue-100 ml-2 p-1 rounded" onClick={refreshLobbies}>Refresh lobbies</button>
      <ul>
        {lobbies.map((lobby) => (
          <li onClick={() => joinLobby(lobby.id)} 
              key={lobby.id}>{lobby.id}</li>
        ))}
      </ul>
    </div>
  );
};