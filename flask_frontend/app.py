#!/usr/bin/env python3
"""
Flask-Frontend für Open Deep Research
Minimaler Server mit SSE-Streaming im Stil des Referenzmaterials
"""
import asyncio
import nest_asyncio

# Allow nested event loops (needed for sync Flask + async LangGraph)
nest_asyncio.apply()
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, Any
from enum import Enum

from flask import Flask, render_template, request, Response, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Add parent directory to path to import deep_researcher
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

# Configure logging for production (Railway) vs development
logging.basicConfig(
    level=logging.INFO if os.getenv('RAILWAY_ENVIRONMENT') else logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Security Configuration
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
APP_PASSWORD = os.getenv('APP_PASSWORD', 'changeme')

# Rate Limiter (gegen Brute-Force) - Disabled for Railway deployment
# Using in-memory storage with gunicorn+gevent can cause deadlocks
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],  # Disabled
    enabled=False
)

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

# Background Job System for long-running research
class JobStatus(Enum):
    """Job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# Job storage: job_id -> {status, event_queue, result, error, created_at, updated_at}
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

def create_job(job_id: str) -> Dict[str, Any]:
    """Create a new job."""
    with jobs_lock:
        if job_id not in jobs:
            jobs[job_id] = {
                "id": job_id,
                "status": JobStatus.PENDING.value,
                "event_queue": Queue(),
                "result": None,
                "error": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_event_id": 0
            }
        return jobs[job_id]

def get_job(job_id: str) -> Dict[str, Any]:
    """Get job by ID."""
    with jobs_lock:
        return jobs.get(job_id)

def update_job_status(job_id: str, status: str, error: str = None):
    """Update job status."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = status
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
            if error:
                jobs[job_id]["error"] = error

def push_job_event(job_id: str, event: str):
    """Push event to job queue."""
    job = get_job(job_id)
    if job:
        with jobs_lock:
            job["last_event_id"] += 1
            event_id = job["last_event_id"]
        # Add event ID to the event
        event_with_id = f"id: {event_id}\n{event}"
        job["event_queue"].put(event_with_id)

def sse_event(event_type: str, data: Any) -> str:
    """Format SSE event."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"

async def stream_research(message: str, thread_id: str):
    """Stream research results via SSE with detailed tool call updates."""
    # Import here to avoid blocking app startup
    from src.open_deep_research.deep_researcher import deep_researcher

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
        "research_supervisor": "Recherche-Koordination",
        "supervisor": "Recherche-Strategie planen",
        "supervisor_tools": "Sub-Recherchen starten",
        "researcher": "Recherche durchführen",
        "researcher_tools": "Quellen analysieren",
        "compress_research": "Erkenntnisse extrahieren",
        "final_report_generation": "Bericht erstellen"
    }

    def get_contextual_tool_name(tool_name: str, tool_input: dict) -> str:
        """Generate contextual display name for tools based on their input."""
        if tool_name in ["tavily_search", "web_search", "tavily_search_results_json"]:
            # Tavily uses "queries" (list) or "query" (string)
            query = tool_input.get("query", "")
            queries = tool_input.get("queries", [])

            # Get first query from list or use single query string
            if queries and isinstance(queries, list):
                query = queries[0]

            # Limit length
            if query and len(query) > 60:
                query = query[:60] + "..."

            return f"Suche: {query}" if query else "Websuche"
        elif tool_name == "ConductResearch":
            topic = tool_input.get("research_topic", "")
            if topic and len(topic) > 60:
                topic = topic[:60] + "..."
            return f"Recherche: {topic}" if topic else "Teilrecherche starten"
        elif tool_name == "think_tool":
            thought = tool_input.get("thought", "")
            preview = thought[:50] + "..." if len(thought) > 50 else thought
            return f"Analysiere: {preview}" if thought else "Nachdenken"
        elif tool_name == "ResearchComplete":
            return "Recherche abschließen"
        return tool_name

    try:
        # Yield thinking indicator
        yield sse_event("thinking", {"status": "started"})

        # Track current research status with hierarchy
        current_step = ""
        active_tools = {}
        active_steps = {}
        step_counter = 0
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

                # Generate contextual display name
                display_name = get_contextual_tool_name(tool_name, tool_input if isinstance(tool_input, dict) else {})

                active_tools[tool_id] = {
                    "name": tool_name,
                    "display_name": display_name,
                    "input": tool_input,
                    "status": "running"
                }

                yield sse_event("tool_call_start", {
                    "id": tool_id,
                    "name": tool_name,
                    "display_name": display_name,
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
                    step_counter += 1
                    step_id = f"step-{step_counter}-{step_name}"
                    german_name = step_names[step_name]

                    # Determine hierarchy level and parent
                    if step_name in ["clarify_with_user", "write_research_brief", "final_report_generation"]:
                        level = 0
                        parent_id = None
                    elif step_name == "research_supervisor":
                        level = 0
                        parent_id = None
                        current_parent = step_id
                    elif step_name == "supervisor":
                        level = 1
                        parent_id = current_parent
                    elif step_name == "supervisor_tools":
                        level = 1
                        parent_id = current_parent
                        current_parent = step_id
                    elif step_name in ["researcher", "researcher_tools", "compress_research"]:
                        level = 2
                        parent_id = current_parent
                    else:
                        level = 0
                        parent_id = None

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
                        "step_name": step_name,  # Send English name for mapping
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
                            "step_name": step_name,  # Send English name for mapping
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
        logger.error(f"Research stream error: {e}", exc_info=True)
        yield sse_event("error", {"error": str(e)})

def run_research_job(job_id: str, message: str, thread_id: str):
    """Run research in background thread and push events to job queue."""
    try:
        update_job_status(job_id, JobStatus.RUNNING.value)

        # Run async research in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Collect all events from stream_research
            async def collect_events():
                async for event in stream_research(message, thread_id):
                    # Push event to job queue
                    push_job_event(job_id, event)

            loop.run_until_complete(collect_events())

            # Mark job as completed
            update_job_status(job_id, JobStatus.COMPLETED.value)
            push_job_event(job_id, sse_event("done", {}))

        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    except Exception as e:
        logger.error(f"Research job failed [job_id={job_id}]: {e}", exc_info=True)
        update_job_status(job_id, JobStatus.FAILED.value, error=str(e))
        push_job_event(job_id, sse_event("error", {"error": str(e)}))

def start_research_background(job_id: str, message: str, thread_id: str):
    """Start research in background thread."""
    thread = threading.Thread(
        target=run_research_job,
        args=(job_id, message, thread_id),
        daemon=True
    )
    thread.start()
    return thread

# Authentication Middleware
@app.before_request
def check_authentication():
    """Check if user is authenticated before allowing access."""
    # Public routes (no auth needed)
    public_routes = ['login', 'static', 'health']

    # Allow public routes and already authenticated users
    if request.endpoint in public_routes or session.get('authenticated'):
        return None

    # Redirect to login
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with password-only authentication."""
    if request.method == 'POST':
        password = request.form.get('password', '')

        if password == APP_PASSWORD:
            session['authenticated'] = True
            session.permanent = True  # Session bleibt bis Browser geschlossen
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Falsches Passwort')

    # If already authenticated, redirect to main page
    if session.get('authenticated'):
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Serve the main frontend."""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return send_from_directory('static', 'index.html')

@app.route('/api/chat/stream')
def chat_stream():
    """SSE endpoint for streaming chat from job queue."""
    if not session.get('authenticated'):
        return jsonify({"error": "Unauthorized"}), 401

    message = request.args.get('message', '')
    thread_id = request.args.get('thread_id', 'default')
    job_id = request.args.get('job_id', '')

    # If no job_id provided, create new job and start research
    if not job_id:
        if not message:
            return jsonify({"error": "No message provided"}), 400

        # Generate job ID from thread_id and timestamp
        job_id = f"{thread_id}-{int(time.time() * 1000)}"
        create_job(job_id)
        start_research_background(job_id, message, thread_id)

    # Get job
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Get Last-Event-ID from request headers BEFORE generate() (Flask request context)
    last_event_id_header = request.headers.get('Last-Event-ID', '0')
    try:
        last_event_id = int(last_event_id_header)
    except ValueError:
        logger.warning(f"Invalid Last-Event-ID header: {last_event_id_header}")
        last_event_id = 0

    def generate():
        """Generate SSE stream from job queue with heartbeat."""
        last_yield_time = time.time()
        heartbeat_interval = 10  # seconds

        # Send job_id to client so it can reconnect
        yield f"data: {json.dumps({'type': 'job_started', 'job_id': job_id})}\n\n"

        while True:
            try:
                # Try to get event from queue with timeout
                event = job["event_queue"].get(timeout=heartbeat_interval)
                last_yield_time = time.time()
                yield event

                # Check if job is done
                if job["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    break

            except Empty:
                # Timeout - send heartbeat
                current_time = time.time()
                if current_time - last_yield_time >= heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_yield_time = current_time

                # Check if job still exists
                if not get_job(job_id):
                    logger.info(f"Job {job_id} no longer exists, closing stream")
                    break

                # Check if job is done
                if job["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/thread/clear/<thread_id>', methods=['POST'])
def clear_thread(thread_id: str):
    """Clear a thread's messages."""
    if not session.get('authenticated'):
        return jsonify({"error": "Unauthorized"}), 401

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

    # Only print startup info in development mode
    if not os.getenv('RAILWAY_ENVIRONMENT'):
        print(f"🚀 Deep Search Flask Frontend")
        print(f"📡 Server läuft auf http://localhost:{port}")
        print(f"💡 Öffne http://localhost:{port} im Browser")
        print(f"🔑 Verwende Gemini 2.5 Flash + Tavily Search")
        print("-" * 50)
    else:
        logger.info(f"Starting Flask app on port {port} in production mode")

    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
