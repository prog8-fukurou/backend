from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import random
import base64
import json
import boto3
import os
from typing import Union
from pydantic import BaseModel
from botocore.exceptions import ClientError

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
                            if len(room.readied) == 2:
                                master_index = random.randint(0, len(room.players) - 1)
                                room.master = list(room.players)[master_index]
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
    backgroundColor: str | None
    belongings: str | None

class ResponseMaterial(BaseModel):
    travel_plan_name: str | None
    travel_place: str | None
    travel_schedule: list[str] | None
    suggested_sightseeing_spots: list[str] | None
    travel_plan_description: str | None
    belongings: list[str] | None
    backgroundColor: str | None
    
@app.post("/prompt")
async def generate_text(prompt: PromptMaterial, try_count: int = 0) -> ResponseMaterial:
    if prompt.purpose is None and prompt.category is None and prompt.overnight is None and prompt.belongings is None:
        raise HTTPException(status_code=422, detail="Please specify at least one parameter.")
    client = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    # Start a conversation with the user message.
    user_message = f"Human:\nあなたは優秀なアシスタントです。\n以下に旅行の資料を添付します。\n\n"
    user_message += f"<document>\n旅の目的:{prompt.purpose}\nどんな場所か:{prompt.category}\n日帰りか泊まりか:{(lambda x: '日帰り' if prompt.overnight == 'True' else '3泊4日')}\n持ち物:{prompt.belongings}</document>\n\n"
    user_message += f"以上の資料をもとに、旅行のプラン名、目的地の名前、持ち物、旅行スケジュール、おすすめの観光スポット、プランの説明を考え、'travel_plan_name','travel_place','travel_schedule','suggested_sightseeing_spots','travel_plan_description','belongings'をキーとしたJSON形式で生成してください。\n\n"
    user_message += f"ただし、旅行スケジュールとおすすめの観光スポットと持ち物は文字列のリスト形式にしてください。目的地や観光スポットは固有名詞にしてください。また、全ての項目は架空のものでも構いません。JSONデータ以外は生成しないでください。"
    user_message += f"Assistant:\n"
    
    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]

    try:
        # Send the message to the model, using a basic inference configuration.
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 2000, "temperature": 1.0, "topP": 0.9},
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
        try:
            json_response = json.loads(response_text)
            prompt_material_response = ResponseMaterial(
                **json_response, 
                backgroundColor=prompt.backgroundColor
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing response: {e}")
            if try_count < 4:
                return await generate_text(prompt, try_count + 1)
            else:
                raise HTTPException(status_code=500, detail="Failed to generate valid text after multiple attempts.")
        return prompt_material_response

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)

    # StreamResponseにしたい
    # https://engineers.safie.link/entry/2022/11/14/fastapi-streaming-response

@app.post("/image")
async def generate_image(prompt: ResponseMaterial):
    prompt_material_response = prompt
    if prompt_material_response.travel_plan_name is None or prompt_material_response.travel_place is None or prompt_material_response.travel_schedule is None or prompt_material_response.suggested_sightseeing_spots is None:
        raise HTTPException(status_code=422, detail="All fields are required.")
    client = boto3.client(service_name="bedrock-runtime", region_name = "us-west-2")
    user_message_ja = f"{prompt_material_response.travel_plan_name}という旅行で、{prompt_material_response.travel_place}という観光地を訪れます。ただし、{prompt_material_response.travel_place}には{','.join(prompt_material_response.suggested_sightseeing_spots)}という観光地があります。\n\n以上の情報を踏まえて、{prompt_material_response.travel_place}のイメージ画像を生成してください。"
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    user_message = f"Human:\nYou are an excellent assistant.\nPlease transrate sentences from Japanese to English.\n Be careful not to change the meaning of words when translating.\n\n<sentences>\n{user_message_ja}</sentences>\n\nAssistant:\n"
    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]
    
    try:
        # Send the message to the model, using a basic inference configuration.
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 2000, "temperature": 0.5, "topP": 0.9},
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
    
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        print("Using original Japanese prompt.")
        response_text = user_message_ja
    
    
    # model_id = "amazon.titan-image-generator-v1"
    model_id = "stability.stable-diffusion-xl-v1"
    seed = random.randint(0, 2147483647)
    user_message = response_text
    print(f"user_message: {user_message}")
    # Format the request payload using the model's native structure.
    # native_request = {
    #     "taskType": "TEXT_IMAGE",
    #     "textToImageParams": {"text": user_message},
    #     "imageGenerationConfig": {
    #         "numberOfImages": 1,
    #         "quality": "standard",
    #         "cfgScale": 8.0,
    #         "height": 768,
    #         "width": 1024,
    #         "seed": seed,
    #     },
    # }
    native_request = {
        "text_prompts": [{"text": user_message}],
        "style_preset": "photographic",
        "seed": seed,
        "cfg_scale": 10,
        "steps": 30,
        "height": 768,
        "width": 1024
    }

    request = json.dumps(native_request)

    response = client.invoke_model(modelId=model_id, body=request)

    model_response = json.loads(response["body"].read())

    # base64_image_data = model_response["images"][0]
    base64_image_data = model_response["artifacts"][0]["base64"]

    
    i, output_dir = 1, "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # while os.path.exists(os.path.join(output_dir, f"titan_{i}.png")):
    #     i += 1
    while os.path.exists(os.path.join(output_dir, f"stablediffusion_{i}.png")):
        i += 1

    image_data = base64.b64decode(base64_image_data)

    # image_path = os.path.join(output_dir, f"titan_{i}.png")
    image_path = os.path.join(output_dir, f"stablediffusion_{i}.png")
    
    with open(image_path, "wb") as file:
        file.write(image_data)
        
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

@app.get("")
async def get():
    return "Hello, World!"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)