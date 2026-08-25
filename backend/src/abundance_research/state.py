"""Graph state and domain data structures for Abundance research runs."""

import operator
from typing import Annotated, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


###################
# Structured Outputs
###################
class InvestigateQuestion(BaseModel):
    """Delegate one bounded evidence or falsification question."""

    evidence_question: str = Field(
        description="A standalone evidence question with scope, source priorities, and the claim it should support or challenge.",
    )

class EvidenceReviewComplete(BaseModel):
    """Signal that material evidence gaps have been investigated."""

class PageSummary(BaseModel):
    """Evidence summary and checkable excerpts from one source."""
    
    summary: str
    key_excerpts: str

class ClarificationDecision(BaseModel):
    """Model for user clarification requests."""
    
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )

class ResearchBrief(BaseModel):
    """Research question and brief for guiding research."""
    
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )


###################
# State Definitions
###################

def replace_or_append(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
    
class InquiryInputState(MessagesState):
    """External workflow input containing the inquiry conversation."""

class ResearchRunState(MessagesState):
    """Main agent state containing messages and research data."""
    
    coordination_messages: Annotated[list[MessageLikeRepresentation], replace_or_append]
    research_brief: Optional[str]
    raw_evidence: Annotated[list[str], replace_or_append] = []
    notes: Annotated[list[str], replace_or_append] = []
    final_report: str

class CoordinationState(TypedDict):
    """State for planning and coordinating evidence questions."""
    
    coordination_messages: Annotated[list[MessageLikeRepresentation], replace_or_append]
    research_brief: str
    notes: Annotated[list[str], replace_or_append] = []
    coordination_iterations: int = 0
    raw_evidence: Annotated[list[str], replace_or_append] = []

class InvestigationState(TypedDict):
    """State for one bounded evidence investigation."""
    
    investigation_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    evidence_question: str
    evidence_dossier: str
    raw_evidence: Annotated[list[str], replace_or_append] = []

class InvestigationOutput(BaseModel):
    """Evidence dossier returned by one investigation."""
    
    evidence_dossier: str
    raw_evidence: Annotated[list[str], replace_or_append] = []
