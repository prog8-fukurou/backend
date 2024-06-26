import boto3
import json
from pydantic import BaseModel

def sample():
    ### 以下サンプルコードです
    bedrock = boto3.client(service_name='bedrock-runtime')

    body = json.dumps({
        "prompt": "\n\nHuman:KDDIアジャイル開発センターってどんな会社？\n\nAssistant:",
        "max_tokens_to_sample": 300,
        "temperature": 0.1,
        "top_p": 0.9,
    })

    modelId = 'anthropic.claude-v2'
    accept = 'application/json'
    contentType = 'application/json'
    # StreamResponseにしたい
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model_with_response_stream.html
    response = bedrock.invoke_model(body=body, modelId=modelId, accept=accept, contentType=contentType)
    response_body = json.loads(response.get('body').read())

    # text
    print(response_body.get('completion'))

class PromptMaterial(BaseModel):
    purpose: str | None
    category: str | None
    overnight: str | None
    background_color: str | None
    belongings: str | None

def aws_generate_text(prompt: PromptMaterial):
    text = ""
    if prompt.purpose is not None:
        text += f"{prompt.purpose}を目的の旅行です。"
    if prompt.category is not None:
        text += f"{prompt.category}的な場所に行ってみるのはいかがでしょうか。"
    if prompt.overnight is not None:
        text += f"{'泊まる予定です。' if prompt.overnight == 'True' else '日帰りする予定です。'}"
    if prompt.belongings is not None:
        text += f"持ち物は{prompt.belongings}を持っていくといいかもしれません"
    return text

def aws_generate_image(prompt: str):
    pass