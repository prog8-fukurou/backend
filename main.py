from mangum import Mangum
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/v1/test")
def test():
    return "Hello, World"

@app.get("/")
def heartbeat():
    return "Success"

handler = Mangum(app)