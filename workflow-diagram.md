# Open Deep Research - Workflow Diagram

## Complete Agent & LLM Call Flow

```mermaid
graph TD
    Start([User Query]) --> Clarify[clarify_with_user]

    Clarify -->|LLM Call 1| ClarifyModel{{"LLM: research_model<br/>Output: ClarifyWithUser"}}
    ClarifyModel -->|need_clarification=true| End1([Return Question])
    ClarifyModel -->|need_clarification=false| Brief[write_research_brief]

    Brief -->|LLM Call 2| BriefModel{{"LLM: research_model<br/>Output: ResearchQuestion"}}
    BriefModel --> SupervisorGraph[/"SUPERVISOR SUBGRAPH"/]

    %% Supervisor Subgraph
    SupervisorGraph --> Supervisor[supervisor]
    Supervisor -->|LLM Call 3| SupervisorModel{{"LLM: research_model<br/>Tools: ConductResearch,<br/>ResearchComplete,<br/>think_tool"}}

    SupervisorModel -->|tool_calls| SupervisorTools[supervisor_tools]

    SupervisorTools -->|think_tool| ThinkReflection["Record reflection<br/>(no LLM call)"]
    ThinkReflection --> Supervisor

    SupervisorTools -->|ConductResearch x N| ParallelResearch{{"Parallel Execution<br/>asyncio.gather()<br/>Max: max_concurrent_research_units"}}

    %% Researcher Subgraph (executed in parallel)
    ParallelResearch --> ResearcherGraph1[/"RESEARCHER SUBGRAPH 1"/]
    ParallelResearch --> ResearcherGraph2[/"RESEARCHER SUBGRAPH 2"/]
    ParallelResearch --> ResearcherGraphN[/"RESEARCHER SUBGRAPH N"/]

    %% Individual Researcher Flow
    ResearcherGraph1 --> Researcher1[researcher]
    Researcher1 -->|LLM Call 4a| ResearcherModel1{{"LLM: research_model<br/>Tools: tavily_search,<br/>web_search, MCP tools,<br/>think_tool"}}

    ResearcherModel1 -->|tool_calls| ResearcherTools1[researcher_tools]

    ResearcherTools1 -->|think_tool| Think1["Record reflection"]
    Think1 --> Researcher1

    ResearcherTools1 -->|search/MCP tools| ParallelTools{{"Parallel Tool Execution<br/>asyncio.gather()"}}
    ParallelTools -->|Tavily| TavilyAPI[("Tavily API")]
    ParallelTools -->|MCP| MCPServer[("MCP Server")]
    ParallelTools -->|OpenAI/Anthropic| WebSearch[("Native Web Search")]

    TavilyAPI -->|results| TavilySummarize{{"LLM: summarization_model<br/>(if content > max_content_length)"}}
    TavilySummarize --> ToolResults1[Tool Results]
    MCPServer --> ToolResults1
    WebSearch --> ToolResults1

    ToolResults1 -->|max_react_tool_calls reached| Compress1[compress_research]
    ToolResults1 -->|continue| Researcher1

    Compress1 -->|LLM Call 5a| CompressModel1{{"LLM: compression_model<br/>Retries on token limit"}}
    CompressModel1 --> CompressedResult1[["Compressed Research<br/>+ Raw Notes"]]

    %% Other researchers follow same pattern
    ResearcherGraph2 --> Researcher2[researcher]
    Researcher2 -->|LLM Call 4b| ResearcherModel2{{"LLM: research_model"}}
    ResearcherModel2 --> ResearcherTools2[researcher_tools]
    ResearcherTools2 --> Compress2[compress_research]
    Compress2 -->|LLM Call 5b| CompressModel2{{"LLM: compression_model"}}
    CompressModel2 --> CompressedResult2[["Compressed Research<br/>+ Raw Notes"]]

    ResearcherGraphN --> ResearcherN[researcher]
    ResearcherN -->|LLM Call 4n| ResearcherModelN{{"LLM: research_model"}}
    ResearcherModelN --> ResearcherToolsN[researcher_tools]
    ResearcherToolsN --> CompressN[compress_research]
    CompressN -->|LLM Call 5n| CompressModelN{{"LLM: compression_model"}}
    CompressModelN --> CompressedResultN[["Compressed Research<br/>+ Raw Notes"]]

    %% Back to Supervisor
    CompressedResult1 --> GatherResults{{"Gather All Results<br/>asyncio.gather()"}}
    CompressedResult2 --> GatherResults
    CompressedResultN --> GatherResults

    GatherResults --> AggregateNotes["Aggregate raw_notes<br/>+ compressed findings"]
    AggregateNotes --> Supervisor

    SupervisorModel -->|ResearchComplete<br/>OR max_researcher_iterations| ExitSupGraph[/"EXIT SUPERVISOR SUBGRAPH"/]

    %% Final Report Generation
    ExitSupGraph --> FinalReport[final_report_generation]
    FinalReport -->|LLM Call 6| FinalReportModel{{"LLM: final_report_model<br/>Retries with 10% truncation<br/>on token limit"}}
    FinalReportModel --> End2([Final Report])

    %% Styling
    classDef llmCall fill:#4f46e5,stroke:#312e81,color:#fff
    classDef node fill:#0ea5e9,stroke:#075985,color:#fff
    classDef subgraph fill:#059669,stroke:#065f46,color:#fff
    classDef external fill:#dc2626,stroke:#991b1b,color:#fff
    classDef result fill:#f59e0b,stroke:#92400e,color:#fff

    class ClarifyModel,BriefModel,SupervisorModel,ResearcherModel1,ResearcherModel2,ResearcherModelN,CompressModel1,CompressModel2,CompressModelN,FinalReportModel,TavilySummarize llmCall
    class Clarify,Brief,Supervisor,SupervisorTools,Researcher1,Researcher2,ResearcherN,ResearcherTools1,ResearcherTools2,ResearcherToolsN,Compress1,Compress2,CompressN,FinalReport node
    class ResearcherGraph1,ResearcherGraph2,ResearcherGraphN,SupervisorGraph,ExitSupGraph subgraph
    class TavilyAPI,MCPServer,WebSearch external
    class CompressedResult1,CompressedResult2,CompressedResultN result
```

## Flow Explanation

### Phase 1: Query Analysis & Planning
1. **clarify_with_user** - LLM Call 1 (research_model)
   - Analyzes if user query needs clarification
   - Returns question OR proceeds to research

2. **write_research_brief** - LLM Call 2 (research_model)
   - Transforms user message into structured research brief
   - Initializes supervisor context

### Phase 2: Supervisor Coordination (Loop)
3. **supervisor** - LLM Call 3 (research_model)
   - Plans research strategy
   - Calls ConductResearch to delegate tasks
   - Uses think_tool for reflection
   - Loops until ResearchComplete or max_researcher_iterations

4. **supervisor_tools**
   - Executes ConductResearch in parallel (asyncio.gather)
   - Max concurrency: max_concurrent_research_units
   - Aggregates results from all researchers

### Phase 3: Individual Research (Parallel Execution)
5. **researcher** - LLM Call 4a-n (research_model)
   - Each researcher works on specific research topic
   - Uses search tools and MCP tools
   - Uses think_tool for strategic planning
   - Loops until max_react_tool_calls reached

6. **researcher_tools**
   - Executes all tool calls in parallel (asyncio.gather)
   - Tavily results may trigger summarization_model
   - Returns tool results to researcher

7. **compress_research** - LLM Call 5a-n (compression_model)
   - Synthesizes researcher findings into concise summary
   - Retries on token limit by removing older messages
   - Returns compressed_research + raw_notes

### Phase 4: Final Report
8. **final_report_generation** - LLM Call 6 (final_report_model)
   - Synthesizes all compressed findings
   - Retries on token limit with 10% truncation per attempt
   - Returns final comprehensive report

## Total LLM Calls

**Minimum**: 6 calls
- 1x clarify_with_user
- 1x write_research_brief
- 1x supervisor
- 1x researcher
- 1x compress_research
- 1x final_report_generation

**Typical**: 15-30 calls
- 1x clarify_with_user
- 1x write_research_brief
- 3-6x supervisor (iterations)
- 3-5x researcher per research unit (3-5 units)
- 3-5x compress_research
- 1x final_report_generation
- 0-10x summarization_model (for long Tavily results)

## Parallel Execution Points

1. **Multiple Researchers**: Up to `max_concurrent_research_units` researchers execute simultaneously
2. **Tool Calls**: Within each researcher, all tool calls execute in parallel
3. **Tavily Summarization**: Happens independently for each search result

## Configuration Impact

- `max_concurrent_research_units`: Controls supervisor parallelism (default: 5)
- `max_researcher_iterations`: Controls supervisor loop (default: 6)
- `max_react_tool_calls`: Controls researcher loop (default: 10)
- `max_structured_output_retries`: Retry count for all LLM calls (default: 3)
