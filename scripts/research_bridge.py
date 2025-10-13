#!/usr/bin/env python3
"""
Research Bridge for Next.js Integration.
Reads JSON from stdin, streams events as JSON to stdout.
"""
import sys
import json
import asyncio
from pathlib import Path

# Add project root and src directory to path so we can import the package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from open_deep_research.deep_researcher import deep_researcher
except ImportError as e:
    # If import fails, print diagnostic info and re-raise
    print(json.dumps({
        "event": "error",
        "error": f"Import failed: {e}",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "sys_path": sys.path,
        "project_root": str(project_root),
        "cwd": str(Path.cwd()),
        "site_packages": [p for p in sys.path if 'site-packages' in p]
    }), flush=True)
    raise


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


async def main():
    """Stream research events from deep_researcher."""
    try:
        # Read input from stdin
        input_data = json.loads(sys.stdin.read())
        message = input_data['message']
        config = input_data['config']

        # Stream events
        async for event in deep_researcher.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            version="v2"
        ):
            # Serialize and output event
            serialized = serialize_event(event)
            print(json.dumps(serialized), flush=True)

        # Signal completion
        print(json.dumps({"event": "done"}), flush=True)

    except Exception as e:
        # Output error
        error_event = {
            "event": "error",
            "error": str(e)
        }
        print(json.dumps(error_event), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
