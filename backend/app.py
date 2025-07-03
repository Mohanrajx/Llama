import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import AsyncGenerator

from core.engine import get_chat_engine

# --- FastAPI App Initialization ---
app = FastAPI()

# --- CORS Middleware ---
# Allows the frontend (running on a different port) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# --- Global Chat Engine ---
# The chat engine is loaded once when the application starts
chat_engine = None

@app.on_event("startup")
def startup_event():
    """Load the chat engine on application startup."""
    global chat_engine
    print("Loading chat engine...")
    chat_engine = get_chat_engine()
    print("Chat engine loaded successfully.")

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chatbot API is running"}

@app.post("/api/chat")
async def stream_chat(request: ChatRequest) -> Response:
    """
    Handles a chat request and streams the response back.
    """
    if chat_engine is None:
        return Response("Error: Chat engine is not available.", status_code=500)

    streaming_response = await chat_engine.astream_chat(request.message)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for token in streaming_response.async_response_gen():
            yield token

    return Response(event_generator(), media_type="text/plain")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
