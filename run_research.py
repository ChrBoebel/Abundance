#!/usr/bin/env python3.11
"""
Simple CLI to run Deep Research with OpenRouter DeepSeek V3.2 Exp
"""
import asyncio
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from src.open_deep_research.deep_researcher import deep_researcher

load_dotenv()

async def run_research(topic: str):
    """Run a research query."""
    # Run the research
    config = {
        "configurable": {
            "research_model": "openrouter:deepseek/deepseek-v3.2-exp",
            "summarization_model": "openrouter:deepseek/deepseek-v3.2-exp",
            "compression_model": "openrouter:deepseek/deepseek-v3.2-exp",
            "final_report_model": "openrouter:deepseek/deepseek-v3.2-exp",
            "search_api": "tavily",  # Change to "none" if no Tavily key
            "allow_clarification": False,
            "max_concurrent_research_units": 3,
        }
    }

    result = await deep_researcher.ainvoke(
        {"messages": [{"role": "user", "content": topic}]},
        config=config
    )

    print(result.get("final_report", "No report generated"))

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3.11 run_research.py 'Your research topic'")
        print("\nExample:")
        print("  python3.11 run_research.py 'What are the latest developments in AI?'")
        sys.exit(1)

    topic = " ".join(sys.argv[1:])
    asyncio.run(run_research(topic))
