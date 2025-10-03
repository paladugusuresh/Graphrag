# main.py
import os
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph_rag.rag import rag_chain
from graph_rag.observability import start_metrics_server, get_logger
from graph_rag.conversation_store import conversation_store
import uuid

with open("config.yaml", 'r') as f:
    cfg = yaml.safe_load(f)

logger = get_logger(__name__)
app = FastAPI(title="GraphRAG")

@app.on_event("startup")
def startup_event():
    conversation_store.init()
    if cfg.get("observability", {}).get("metrics_enabled", True):
        start_metrics_server()

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.question:
        raise HTTPException(400, "Question is required")

    conv_id = req.conversation_id if req.conversation_id else str(uuid.uuid4())
    
    conversation_store.add_message(conv_id, {"role": "user", "text": req.question})

    try:
        resp = rag_chain.invoke(req.question)
        conversation_store.add_message(conv_id, {"role": "assistant", "text": resp.get("answer"), "trace_id": resp.get("trace_id")})
        resp["conversation_id"] = conv_id
        return resp
    except Exception as e:
        logger.error(f"Error in /api/chat: {e}")
        raise HTTPException(500, "internal error")

@app.get("/api/chat/{conversation_id}/history")
def get_history(conversation_id: str):
    history = conversation_store.get_history(conversation_id)
    if not history:
        raise HTTPException(404, "Conversation not found")
    return history
