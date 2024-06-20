from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import random

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str) -> None:
        self.active_connections.pop(client_id)

    async def send_personal_message(self, message: str, client_id: str) -> None:
        await self.active_connections[client_id].send_text(message)

class Room:
    def __init__(self, room_id, initiator: str):
        self.room_id = room_id
        self.initiator = initiator
        self.players = set()
        self.readied = set() # 準備ができたプレイヤー
        self.gameend_players = set() # ゲームを終了したプレイヤー
        self.voteend_players = set() # 投票を終了したプレイヤー
        self.voted = list # ユーザーが投票したユーザー(client_id)

    def add_player(self, client_id):
        self.players.add(client_id)

    def remove_player(self, client_id):
        self.players.remove(client_id)

    def add_gameend_player(self, client_id):
        self.gameend_players.add(client_id)
        if len(self.gameend_players) == len(self.players):
            return True
        else:
            return False
    
    def add_voteend_player(self, client_id, vote_id: str):
        self.voteend_players.add(client_id)
        self.voted.append(vote_id)
        if len(self.voteend_players) == len(self.players):
            return True
        else:
            return False
    
    def get_winner(self):
        return max(set(self.voted), key=self.voted.count)

    async def broadcast_message(self, message):
        for player in self.players:
            await ws_manager.send_personal_message(message, player)

ws_manager = ConnectionManager()
rooms = {}
generated_images = {}
#{
#  "room_id": {
#     "client_id": image,
#  }
#}

# Websocket 通信
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: str, room_id: int | None = None):
    await ws_manager.connect(websocket, client_id)
    print(f"Client {client_id} connected to the websocket")
    if room_id is None:
        room_id = random.randint(1000, 9999)
        await websocket.send_text(f"system > Your room ID is: {room_id}")

    if room_id not in rooms:
        rooms[room_id] = Room(room_id, client_id)
    room = rooms[room_id]
    room.add_player(client_id)
    await room.broadcast_message(f"system > New player in the room: {client_id}")

    try:
        while True:
            msg = await websocket.receive_text()
            match msg:
                case "user-init":
                    await websocket.send_text(f"{client_id}:{msg}")
                case "user-ready":
                    room.readied.add(client_id)
                    if len(room.readied) == len(room.players):
                        await room.broadcast_message("game-start")
                case "game-end":
                    flag = room.add_gameend_player(client_id)
                    if flag:
                        await room.broadcast_message("vote-start")
                case "vote-end":
                    flag = room.add_voteend_player(client_id)
                    if flag:
                        winner = room.get_winner()
                        await room.broadcast_message(f"result:{winner}")
                case _:
                    pass
            
            await room.broadcast_message(f"{client_id} > {msg}")
    except WebSocketDisconnect:
        room.remove_player(client_id)
        if not room.players:
            rooms.pop(room_id)

@app.post("/prompt")
async def generate_text(prompt: str):
    # StreamResponseにしたい
    # https://engineers.safie.link/entry/2022/11/14/fastapi-streaming-response
    return {"prompt": prompt}

@app.post("/image")
async def generate_image():
    return {"image": "image"}

@app.get("/all")
async def get_image(room_id: str, client_id: str | None = None):
    if client_id is None:
        return generated_images[room_id]
    else:
        return generated_images[room_id][client_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)