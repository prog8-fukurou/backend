from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import random
import base64
import json
import boto3
import os
from typing import Union
from pydantic import BaseModel

from utils.aws import aws_generate_image, aws_generate_text

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        self.master = None
        self.players = set()
        self.readied = set() # 準備ができたプレイヤー
        self.gameend_players = set() # ゲームを終了したプレイヤー
        self.voteend_players = set() # 投票を終了したプレイヤー
        self.voted_players = [] # 投票結果

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
        self.voted_players.append(vote_id)
        if len(self.voteend_players) == len(self.players):
            return True
        else:
            return False

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
    if room_id is None:
        def generate_room_id():
            room_id = random.randint(1000, 9999)
            if room_id in rooms:
                room_id = generate_room_id()
            return room_id
        room_id = generate_room_id()
        await websocket.send_text(f"room-init:{room_id}")

    if room_id not in rooms:
        rooms[room_id] = Room(room_id)
    room = rooms[room_id]
    room.add_player(client_id)
    await room.broadcast_message(f"user-join:{len(room.players)}")

    try:
        while True:
            msg = await websocket.receive_text()
            match msg.split(":")[0]:
                case "user-init":
                    await room.broadcast_message(f"{client_id}:{msg.split(':')[1]}")
                case "user-ready":
                    room.readied.add(client_id)
                    if ":" in msg:
                        if msg.split(":")[1] == "debug:master":
                            if len(room.readied) == 2:
                                room.master = client_id
                                await room.broadcast_message(f"game-start:{room.master}")
                    else:
                        if len(room.readied) == 4:
                            master_index = random.randint(0, len(room.players) - 1)
                            room.master = list(room.players)[master_index]
                            await room.broadcast_message(f"game-start:{room.master}")
                case "game-end":
                    flag = room.add_gameend_player(client_id)
                    if flag:
                        await room.broadcast_message("vote-start")
                case "vote-end":
                    #flag = room.add_voteend_player(client_id)
                    #if flag:
                    await room.broadcast_message(f"result:{msg.split(':')[1]}")
                case _:
                    await room.broadcast_message(msg)
    
    except WebSocketDisconnect:
        await room.broadcast_message(f"game-interrupted")
        rooms.pop(room_id)

class PromptMaterial(BaseModel):
    purpose: str | None
    category: str | None
    overnight: str | None
    background_color: str | None
    belongings: str | None

@app.post("/prompt")
async def generate_text(prompt: PromptMaterial):
    if prompt.purpose is None and prompt.category is None and prompt.overnight is None and prompt.belongings is None:
        raise HTTPException(status_code=422, detail="Please specify at least one parameter.")
    # StreamResponseにしたい
    # https://engineers.safie.link/entry/2022/11/14/fastapi-streaming-response
    text = aws_generate_text(prompt)
    return text

@app.post("/image")
async def generate_image(prompt: str):
    client = boto3.client(service_name="bedrock-runtime", region_name = os.environ['AWS_DEFAULT_REGION'])
    model_id = "amazon.titan-image-generator-v1"
    seed = random.randint(0, 2147483647)
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

@app.get("/image")
async def get_image(room_id: str, client_id: str | None = None):
    if client_id is None:
        return generated_images[room_id]
    else:
        return generated_images[room_id][client_id]

@app.post("/result")
async def post_result(room_id: str, image: UploadFile = File()):
    generated_images[room_id] = image
    return "OK"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)