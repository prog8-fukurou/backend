from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import random
import base64
import json
import boto3
import os

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
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = set()

    def add_player(self, client_id):
        self.players.add(client_id)

    def remove_player(self, client_id):
        self.players.remove(client_id)

    async def broadcast_message(self, message):
        print(self.players)
        for player in self.players:
            await ws_manager.send_personal_message(message, player)

ws_manager = ConnectionManager()
rooms = {}

# Websocket 通信
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: str, room_id: int | None = None):
    await ws_manager.connect(websocket, client_id)
    print(f"Client {client_id} connected to the websocket")
    if room_id is None:
        room_id = random.randint(1000, 9999)
        await websocket.send_text(f"system > Your room ID is: {room_id}")

    if room_id not in rooms:
        rooms[room_id] = Room(room_id)
    print(rooms)
    room = rooms[room_id]
    room.add_player(client_id)
    await room.broadcast_message(f"system > New player in the room: {client_id}")

    try:
        while True:
            msg = await websocket.receive_text()
            print(f"Client {client_id} says: {msg}")
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
    client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    model_id = "amazon.titan-image-generator-v1"
    seed = random.randint(0, 2147483647)
    # ユーザから取得したもの
    prompt = "京都の夜景"
    # Format the request payload using the model's native structure.
    native_request = {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt},
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "quality": "standard",
            "cfgScale": 8.0,
            "height": 512,
            "width": 512,
            "seed": seed,
        },
    }

    request = json.dumps(native_request)

    response = client.invoke_model(modelId=model_id, body=request)

    model_response = json.loads(response["body"].read())

    base64_image_data = model_response["images"][0]
    
    # i, output_dir = 1, "output"
    # if not os.path.exists(output_dir):
    #     os.makedirs(output_dir)
    # while os.path.exists(os.path.join(output_dir, f"titan_{i}.png")):
    #     i += 1

    # image_data = base64.b64decode(base64_image_data)

    # image_path = os.path.join(output_dir, f"titan_{i}.png")
    # with open(image_path, "wb") as file:
    #     file.write(image_data)
        
    return {"image": base64_image_data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)