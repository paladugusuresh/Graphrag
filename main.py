# main.py
import os
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph_rag.rag import rag_chain
from graph_rag.observability import start_metrics_server, get_logger

with open("config.yaml", 'r') as f:
    cfg = yaml.safe_load(f)

logger = get_logger(__name__)
app = FastAPI(title="GraphRAG")

if cfg.get("observability", {}).get("metrics_enabled", True):
    start_metrics_server()

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.question:
        raise HTTPException(400, "Question is required")
    try:
        resp = rag_chain.invoke(req.question)
        return resp
    except Exception as e:
        logger.error(f"Error in /api/chat: {e}")
        raise HTTPException(500, "internal error")
