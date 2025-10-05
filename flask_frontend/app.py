#!/usr/bin/env python3
"""
Flask-Frontend für Open Deep Research
Minimaler Server mit SSE-Streaming im Stil des Referenzmaterials
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Dict, Any

from flask import Flask, render_template, request, Response, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent directory to path to import deep_researcher
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.open_deep_research.deep_researcher import deep_researcher

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# In-memory thread storage
threads: Dict[str, Dict[str, Any]] = {}

def get_thread(thread_id: str) -> Dict[str, Any]:
    """Get or create a thread."""
    if thread_id not in threads:
        threads[thread_id] = {
            "id": thread_id,
            "messages": [],
            "created_at": datetime.now().isoformat()
        }
    return threads[thread_id]

def sse_event(event_type: str, data: Any) -> str:
    """Format SSE event."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"

async def stream_research(message: str, thread_id: str):
    """Stream research results via SSE with detailed tool call updates."""
    thread = get_thread(thread_id)

    # Add user message to thread
    thread["messages"].append({
        "role": "user",
        "content": message
    })

    # Prepare config for deep researcher
    config = {
        "configurable": {
            "research_model": "google_genai:models/gemini-2.5-flash",
            "summarization_model": "google_genai:models/gemini-2.5-flash",
            "compression_model": "google_genai:models/gemini-2.5-flash",
            "final_report_model": "google_genai:models/gemini-2.5-flash",
            "search_api": "tavily",
            "allow_clarification": False,
            "max_concurrent_research_units": 3,
        }
    }

    # German names for workflow steps
    step_names = {
        "clarify_with_user": "Frage analysieren",
        "write_research_brief": "Recherche-Plan erstellen",
        "research_supervisor": "Recherche koordinieren",
        "supervisor": "Recherche-Strategie entwickeln",
        "supervisor_tools": "Recherche delegieren",
        "researcher": "Informationen sammeln",
        "researcher_tools": "Quellen durchsuchen",
        "compress_research": "Ergebnisse zusammenfassen",
        "final_report_generation": "Abschlussbericht erstellen"
    }

    try:
        # Yield thinking indicator
        yield sse_event("thinking", {"status": "started"})

        # Track current research status with hierarchy
        current_step = ""
        active_tools = {}
        active_steps = {}
        step_counter = 0
        seen_steps = set()  # Deduplicate steps
        step_hierarchy = {}  # Track parent-child relationships
        current_parent = None  # Current parent step for nesting
        final_report_sent = False  # Prevent duplicate final reports

        # Stream research - using astream_events for granular updates
        async for event in deep_researcher.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            version="v2"
        ):
            event_type = event.get("event", "")
            event_name = event.get("name", "")

            # Tool execution started
            if event_type == "on_tool_start":
                tool_name = event_name
                tool_id = event.get("run_id", "")
                tool_input = event.get("data", {}).get("input", {})

                # Convert tool_input to string if it's not JSON serializable
                if tool_input and not isinstance(tool_input, (str, int, float, bool, type(None), dict, list)):
                    tool_input = str(tool_input)

                active_tools[tool_id] = {
                    "name": tool_name,
                    "input": tool_input,
                    "status": "running"
                }

                yield sse_event("tool_call_start", {
                    "id": tool_id,
                    "name": tool_name,
                    "args": tool_input,
                    "status": "running",
                    "parent_id": current_parent,
                    "level": 2  # Tools are always level 2
                })

            # Tool execution completed
            elif event_type == "on_tool_end":
                tool_id = event.get("run_id", "")
                tool_output = event.get("data", {}).get("output", "")

                # Convert tool_output to string if it's not JSON serializable
                if tool_output and not isinstance(tool_output, (str, int, float, bool, type(None), dict, list)):
                    tool_output = str(tool_output)

                if tool_id in active_tools:
                    active_tools[tool_id]["status"] = "completed"
                    active_tools[tool_id]["result"] = tool_output

                    yield sse_event("tool_call_complete", {
                        "id": tool_id,
                        "name": active_tools[tool_id]["name"],
                        "result": tool_output,
                        "status": "completed"
                    })

            # Tool execution error
            elif event_type == "on_tool_error":
                tool_id = event.get("run_id", "")
                error = event.get("data", {}).get("error", "Unknown error")

                if tool_id in active_tools:
                    active_tools[tool_id]["status"] = "error"

                    yield sse_event("tool_call_complete", {
                        "id": tool_id,
                        "name": active_tools[tool_id]["name"],
                        "error": str(error),
                        "status": "error"
                    })

            # Chain/Node execution started (research steps)
            elif event_type == "on_chain_start":
                step_name = event_name
                if step_name and step_name in step_names:
                    # Deduplicate: only show each unique step once
                    if step_name in seen_steps:
                        continue

                    seen_steps.add(step_name)
                    step_counter += 1
                    step_id = f"step-{step_counter}-{step_name}"
                    german_name = step_names[step_name]

                    # Determine hierarchy level
                    level = 0  # Default to top-level
                    parent_id = None

                    if step_name in ["researcher", "researcher_tools", "compress_research"]:
                        level = 1  # Sub-researchers
                        parent_id = current_parent if current_parent else None
                    elif step_name in ["supervisor", "supervisor_tools"]:
                        level = 0
                        current_parent = step_id  # This becomes parent for sub-steps
                    elif step_name == "research_supervisor":
                        level = 0
                        current_parent = step_id

                    active_steps[step_id] = {
                        "name": step_name,
                        "german_name": german_name,
                        "status": "running",
                        "parent_id": parent_id,
                        "level": level
                    }

                    yield sse_event("step_start", {
                        "id": step_id,
                        "name": german_name,
                        "status": "running",
                        "parent_id": parent_id,
                        "level": level
                    })
                    current_step = step_name

            # Stream AI message chunks
            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        yield sse_event("chunk", {"content": str(content)})

            # Chain completed - check for final report
            elif event_type == "on_chain_end":
                step_name = event_name

                # Mark step as complete if tracked
                if step_name and step_name in step_names:
                    # Find the most recent step with this name
                    matching_steps = [sid for sid in active_steps.keys() if step_name in sid]
                    if matching_steps:
                        latest_step_id = matching_steps[-1]
                        active_steps[latest_step_id]["status"] = "completed"

                        yield sse_event("step_complete", {
                            "id": latest_step_id,
                            "name": step_names[step_name],
                            "status": "completed"
                        })

                # Check for final report (only send once)
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict) and "final_report" in output and not final_report_sent:
                    final_report = output["final_report"]
                    final_report_sent = True  # Mark as sent
                    # Add to thread
                    thread["messages"].append({
                        "role": "assistant",
                        "content": final_report
                    })
                    # Send complete message
                    yield sse_event("agent_message", {"content": final_report})

        # Signal completion
        yield sse_event("done", {})

    except Exception as e:
        yield sse_event("error", {"error": str(e)})

@app.route('/')
def index():
    """Serve the main frontend."""
    return send_from_directory('static', 'index.html')

@app.route('/api/chat/stream')
def chat_stream():
    """SSE endpoint for streaming chat."""
    message = request.args.get('message', '')
    thread_id = request.args.get('thread_id', 'default')

    if not message:
        return jsonify({"error": "No message provided"}), 400

    def generate():
        """Generate SSE stream."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = stream_research(message, thread_id)
            while True:
                try:
                    item = loop.run_until_complete(async_gen.__anext__())
                    yield item
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/thread/clear/<thread_id>', methods=['POST'])
def clear_thread(thread_id: str):
    """Clear a thread's messages."""
    if thread_id in threads:
        threads[thread_id]["messages"] = []
    return jsonify({"status": "cleared"})

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "threads": len(threads),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4290))
    print(f"🚀 Deep Search Flask Frontend")
    print(f"📡 Server läuft auf http://localhost:{port}")
    print(f"💡 Öffne http://localhost:{port} im Browser")
    print(f"🔑 Verwende Gemini 2.5 Flash + Tavily Search")
    print("-" * 50)
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
