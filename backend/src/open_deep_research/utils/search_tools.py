"""Search tool implementations (Tavily, arXiv, PubMed)."""

import asyncio
import logging
from typing import Annotated, List, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from tavily import AsyncTavilyClient

from open_deep_research.configuration import Configuration
from open_deep_research.prompts import summarize_webpage_prompt
from open_deep_research.state import Summary
from open_deep_research.utils.model_utils import (
    init_chat_model_wrapper,
    get_api_key_for_model,
    get_tavily_api_key,
    get_today_str,
    create_cached_message,
)


##########################
# Search Tools
##########################

TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)


@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_search_results: Annotated[int, InjectedToolArg] = 10,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    config: RunnableConfig = None
) -> str:
    """Fetch and summarize search results from Tavily search API.

    Args:
        queries: List of search queries to execute
        max_search_results: Maximum number of results to return per query
        topic: Topic filter for search results (general, news, or finance)
        config: Runtime configuration for API keys and model settings

    Returns:
        Formatted string containing summarized search results
    """
    # Step 1: Execute search queries asynchronously
    search_results = await tavily_search_async(
        queries,
        max_results=max_search_results,
        topic=topic,
        include_raw_content=True,
        config=config
    )

    # Step 2: Deduplicate results by URL to avoid processing the same content multiple times
    unique_results = {}
    for response in search_results:
        for result in response['results']:
            url = result['url']
            if url not in unique_results:
                unique_results[url] = {**result, "query": response['query']}

    # Step 3: Set up the summarization model with configuration
    configurable = Configuration.from_runnable_config(config)

    # Character limit to stay within model token limits (configurable)
    max_char_to_include = configurable.max_content_length

    # Initialize summarization model with retry logic
    model_api_key = get_api_key_for_model(configurable.summarization_model, config)
    summarization_model = init_chat_model_wrapper(
        model=configurable.summarization_model,
        max_tokens=configurable.summarization_model_max_tokens,
        api_key=model_api_key,
        tags=["langsmith:nostream"]
    ).with_structured_output(Summary).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    )

    # Step 4: Create summarization tasks (skip empty content)
    async def noop():
        """No-op function for results without raw content."""
        return None

    summarization_tasks = [
        noop() if not result.get("raw_content")
        else summarize_webpage(
            summarization_model,
            result['raw_content'][:max_char_to_include],
            enable_caching=configurable.enable_prompt_caching
        )
        for result in unique_results.values()
    ]

    # Step 5: Execute all summarization tasks in parallel
    summaries = await asyncio.gather(*summarization_tasks)

    # Step 6: Combine results with their summaries
    summarized_results = {
        url: {
            'title': result['title'],
            'content': result['content'] if summary is None else summary
        }
        for url, result, summary in zip(
            unique_results.keys(),
            unique_results.values(),
            summaries
        )
    }

    # Step 7: Format the final output
    if not summarized_results:
        return "No valid search results found. Please try different search queries or use a different search API."

    formatted_output = "Search results: \n\n"
    for i, (url, result) in enumerate(summarized_results.items()):
        formatted_output += f"\n\n--- SOURCE {i+1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        formatted_output += "\n\n" + "-" * 80 + "\n"

    return formatted_output


ARXIV_SEARCH_DESCRIPTION = (
    "Search scientific papers on arXiv.org covering physics, mathematics, computer science, "
    "quantitative biology, quantitative finance, statistics, electrical engineering, and economics. "
    "Returns peer-reviewed papers with abstracts and full-text access."
)


@tool(description=ARXIV_SEARCH_DESCRIPTION)
async def arxiv_search(queries: List[str], config: RunnableConfig = None) -> str:
    """Search and retrieve scientific papers from arXiv.

    Args:
        queries: List of search queries to execute
        config: Runtime configuration

    Returns:
        Formatted string containing arXiv search results
    """
    from langchain_community.retrievers import ArxivRetriever

    retriever = ArxivRetriever(load_max_docs=10, get_full_documents=True)

    # Execute search for all queries
    all_results = []
    for query in queries:
        try:
            results = retriever.invoke(query)
            all_results.extend(results)
        except Exception as e:
            logging.debug(f"arXiv search failed for query '{query}': {e}")

    if not all_results:
        return "No arXiv papers found. Try different search terms."

    # Format results like tavily_search
    formatted_output = "arXiv search results:\n\n"
    for i, doc in enumerate(all_results[:10]):
        title = doc.metadata.get('Title', 'Unknown Title')
        url = doc.metadata.get('entry_id', '#')
        authors = doc.metadata.get('Authors', 'Unknown Authors')
        summary = doc.page_content[:800] if doc.page_content else doc.metadata.get('Summary', '')[:800]

        formatted_output += f"\n\n--- SOURCE {i+1}: {title} ---\n"
        formatted_output += f"URL: {url}\n"
        formatted_output += f"Authors: {authors}\n\n"
        formatted_output += f"SUMMARY:\n{summary}...\n\n"
        formatted_output += "\n" + "-" * 80 + "\n"

    return formatted_output


PUBMED_SEARCH_DESCRIPTION = (
    "Search biomedical literature on PubMed comprising more than 35 million citations from "
    "MEDLINE, life science journals, and online books. Useful for medical, health, and "
    "biomedical research questions."
)


@tool(description=PUBMED_SEARCH_DESCRIPTION)
async def pubmed_search(queries: List[str], config: RunnableConfig = None) -> str:
    """Search and retrieve biomedical papers from PubMed.

    Args:
        queries: List of search queries to execute
        config: Runtime configuration

    Returns:
        Formatted string containing PubMed search results
    """
    from langchain_community.retrievers import PubMedRetriever

    retriever = PubMedRetriever(top_k_results=10)

    # Execute search for all queries
    all_results = []
    for query in queries:
        try:
            results = retriever.invoke(query)
            all_results.extend(results)
        except Exception as e:
            logging.debug(f"PubMed search failed for query '{query}': {e}")

    if not all_results:
        return "No PubMed articles found. Try different search terms."

    # Format results like tavily_search
    formatted_output = "PubMed search results:\n\n"
    for i, doc in enumerate(all_results[:10]):
        title = doc.metadata.get('Title', 'Unknown Title')
        uid = doc.metadata.get('uid', '')
        url = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/" if uid else '#'
        summary = doc.page_content[:800] if doc.page_content else ''

        formatted_output += f"\n\n--- SOURCE {i+1}: {title} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{summary}...\n\n"
        formatted_output += "\n" + "-" * 80 + "\n"

    return formatted_output


##########################
# Search Helpers
##########################

async def tavily_search_async(
    search_queries,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = True,
    config: RunnableConfig = None
):
    """Execute multiple Tavily search queries asynchronously.

    Args:
        search_queries: List of search query strings to execute
        max_results: Maximum number of results per query
        topic: Topic category for filtering results
        include_raw_content: Whether to include full webpage content
        config: Runtime configuration for API key access

    Returns:
        List of search result dictionaries from Tavily API
    """
    # Initialize the Tavily client with API key from config
    tavily_client = AsyncTavilyClient(api_key=get_tavily_api_key(config))

    # Create search tasks for parallel execution
    search_tasks = [
        tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic
        )
        for query in search_queries
    ]

    # Execute all search queries in parallel and return results
    search_results = await asyncio.gather(*search_tasks)
    return search_results


async def summarize_webpage(model: BaseChatModel, webpage_content: str, enable_caching: bool = True) -> str:
    """Summarize webpage content using AI model with timeout protection.

    Args:
        model: The chat model configured for summarization
        webpage_content: Raw webpage content to be summarized
        enable_caching: Whether to enable prompt caching for summarization

    Returns:
        Formatted summary with key excerpts, or original content if summarization fails
    """
    try:
        # Create prompt with current date context
        prompt_content = summarize_webpage_prompt.format(
            webpage_content=webpage_content,
            date=get_today_str()
        )

        # Use cached message for summarization prompt (format is consistent)
        message = create_cached_message(HumanMessage, prompt_content, enable_caching)

        # Execute summarization with timeout to prevent hanging
        summary = await asyncio.wait_for(
            model.ainvoke([message]),
            timeout=60.0  # 60 second timeout for summarization
        )

        # Format the summary with structured sections
        formatted_summary = (
            f"<summary>\n{summary.summary}\n</summary>\n\n"
            f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
        )

        return formatted_summary

    except asyncio.TimeoutError:
        # Timeout during summarization - return original content
        logging.warning(f"Summarization timed out after 60 seconds for content length {len(webpage_content)}, returning original content")
        return webpage_content
    except Exception as e:
        # Other errors during summarization - log and return original content
        logging.warning(f"Summarization failed: {type(e).__name__}: {str(e)}, returning original content")
        return webpage_content
