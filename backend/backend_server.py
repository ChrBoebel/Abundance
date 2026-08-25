#!/usr/bin/env python3
"""FastAPI and SSE entrypoint for Abundance research runs."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

# Support direct local execution without requiring an editable install.
backend_root = Path(__file__).parent
sys.path.insert(0, str(backend_root / "src"))

from abundance_research import __version__
from abundance_research.domain import ResearchMode
from abundance_research.events import ResearchEvent, ResearchEventMapper
from abundance_research.workflow import abundance_workflow

app = FastAPI(
    title="Abundance Research API",
    description="Evidence-oriented research orchestration for Abundance.",
    version=__version__,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4290", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    """Legacy research request payload."""
    message: str
    model: str = "mercury"


class ResearchRunRequest(BaseModel):
    """Public request contract for a new Abundance research run."""

    inquiry: str
    model: str = "mercury"
    mode: ResearchMode = ResearchMode.BALANCED


# Mapping from frontend model keys to OpenRouter model IDs
MODEL_MAP = {
    "mercury": "openrouter:inception/mercury-2",
    "gemini-flash": "openrouter:google/gemini-2.5-flash",
    "gemini": "openrouter:google/gemini-2.5-flash-lite",
    "deepseek": "openrouter:deepseek/deepseek-v3.2",
    "glm": "openrouter:z-ai/glm-4.5-air:free",
}


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


RESEARCH_PROFILES = {
    ResearchMode.QUICK: {
        "max_concurrent_research_units": 1,
        "max_researcher_iterations": 2,
        "max_react_tool_calls": 3,
    },
    ResearchMode.BALANCED: {
        "max_concurrent_research_units": 3,
        "max_researcher_iterations": 3,
        "max_react_tool_calls": 4,
    },
    ResearchMode.THOROUGH: {
        "max_concurrent_research_units": 5,
        "max_researcher_iterations": 5,
        "max_react_tool_calls": 8,
    },
}


def build_workflow_config(model: str, mode: ResearchMode = ResearchMode.BALANCED):
    """Build runtime configuration from a product-level research profile."""

    model_id = MODEL_MAP.get(model, MODEL_MAP["mercury"])
    return {
        "configurable": {
            "research_model": model_id,
            "summarization_model": model_id,
            "compression_model": model_id,
            "final_report_model": model_id,
            "search_api": "tavily",
            "allow_clarification": False,
            **RESEARCH_PROFILES[mode],
        }
    }


async def stream_graph_events(
    message: str,
    model: str = "mercury",
    mode: ResearchMode = ResearchMode.BALANCED,
):
    """Stream legacy graph events for backwards compatibility."""
    try:
        config = build_workflow_config(model, mode)

        # Stream events from abundance_workflow
        async for event in abundance_workflow.astream_events(
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


async def stream_abundance_events(request: ResearchRunRequest):
    """Stream framework-independent Abundance events as SSE."""

    mapper = ResearchEventMapper()
    try:
        config = build_workflow_config(request.model, request.mode)
        async for raw_event in abundance_workflow.astream_events(
            {"messages": [{"role": "user", "content": request.inquiry}]},
            config=config,
            version="v2",
        ):
            serialized = serialize_event(raw_event)
            for event in mapper.map(serialized):
                yield f"data: {event.model_dump_json(exclude_none=True)}\n\n"

        completed = ResearchEvent(
            type="run.completed",
            message="Recherche abgeschlossen",
        )
        yield f"data: {completed.model_dump_json(exclude_none=True)}\n\n"
    except Exception as exc:
        failed = ResearchEvent(
            type="run.failed",
            message="Recherche fehlgeschlagen",
            data={"error": str(exc)},
        )
        yield f"data: {failed.model_dump_json(exclude_none=True)}\n\n"


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
        stream_graph_events(request.message, request.model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/v1/research-runs/stream")
async def research_run_stream(request: ResearchRunRequest):
    """Create a research run and stream stable Abundance domain events."""

    if not request.inquiry.strip():
        raise HTTPException(status_code=400, detail="Inquiry is required")

    return StreamingResponse(
        stream_abundance_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
