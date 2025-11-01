#!/usr/bin/env python3
"""
FastAPI Backend Server for Deep Research.
Provides SSE streaming endpoint for research queries.
"""
import sys
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from open_deep_research.deep_researcher import deep_researcher

app = FastAPI(title="Deep Research Backend", version="1.0.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4290", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    """Research request payload."""
    message: str


def serialize_event(event):
    """Serialize event to JSON-compatible format."""
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert(item) for item in obj]
        elif hasattr(obj, 'content'):
            # Extract clean text content from LangChain message objects
            return obj.content
        elif hasattr(obj, '__dict__'):
            # Convert objects to string representation
            return str(obj)
        else:
            return obj

    return convert(event)


async def stream_research_events(message: str):
    """Stream research events as SSE."""
    try:
        # Hardcoded model: Gemini 2.5 Flash via OpenRouter
        model_id = "openrouter:google/gemini-2.5-flash"

        # Build configuration with single model for all roles
        config = {
            "configurable": {
                "research_model": model_id,
                "summarization_model": model_id,
                "compression_model": model_id,
                "final_report_model": model_id,
                "search_api": "tavily",
                "allow_clarification": False,
                "max_concurrent_research_units": 3,
            }
        }

        # Stream events from deep_researcher
        async for event in deep_researcher.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            version="v2"
        ):
            # Serialize and yield as SSE
            serialized = serialize_event(event)
            yield f"data: {json.dumps(serialized)}\n\n"

        # Signal completion
        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    except Exception as e:
        # Output error as SSE event
        error_event = {
            "event": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_event)}\n\n"


@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """
    Stream research events via Server-Sent Events.

    Request Body:
    {
        "message": "Your research question"
    }

    Response: SSE stream with JSON events
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is required")

    return StreamingResponse(
        stream_research_events(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
