"""
Email Triage Environment Models
Strict Pydantic models for type safety and OpenEnv compliance.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class EmailCategory(str, Enum):
    """Valid email categories."""
    SPAM = "spam"
    URGENT = "urgent"
    FOLLOW_UP = "follow_up"
    INFORMATIONAL = "informational"


class Email(BaseModel):
    """Represents a single email in the inbox."""
    email_id: str = Field(..., description="Unique identifier for the email")
    sender: str = Field(..., description="Sender email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content (first 500 chars)")
    timestamp: int = Field(..., description="Unix timestamp of email receipt")
    has_attachment: bool = Field(..., description="Whether email contains attachments")
    is_flagged: bool = Field(False, description="Whether sender is marked as important")


class Observation(BaseModel):
    """Observation of the environment state."""
    current_email: Email = Field(..., description="Current email being triaged")
    inbox_remaining: int = Field(..., description="Number of emails left to process")
    correctly_classified: int = Field(..., description="Count of correctly classified emails so far")
    total_processed: int = Field(..., description="Total emails processed in this episode")
    task_difficulty: str = Field(..., description="Current task difficulty level (easy, medium, hard)")


class TriageAction(BaseModel):
    """Action: classify an email into a category."""
    email_id: str = Field(..., description="ID of the email being classified")
    category: EmailCategory = Field(..., description="Classification category: spam, urgent, follow_up, or informational")
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence level in this classification (0.0 to 1.0)"
    )


class Reward(BaseModel):
    """Reward signal from the environment."""
    value: float = Field(..., description="Scalar reward value")
    breakdown: dict = Field(
        default_factory=dict,
        description="Breakdown of reward components (correctness, confidence, speed)"
    )


class State(BaseModel):
    """Internal state of the environment."""
    episode_id: str = Field(..., description="Unique episode identifier")
    task_type: str = Field(..., description="Current task type (easy, medium, hard)")
    emails_in_inbox: List[Email] = Field(..., description="All emails in current inbox")
    current_email_idx: int = Field(..., description="Index of current email being processed")
    correctly_classified: int = Field(0, description="Number of emails correctly classified")
    total_processed: int = Field(0, description="Total emails processed in this episode")
    classifications: dict = Field(
        default_factory=dict, 
        description="Mapping of email_id to {category, confidence}"
    )
    ground_truth: dict = Field(
        default_factory=dict,
        description="Mapping of email_id to correct category (hidden from agent)"
    )
    episode_done: bool = Field(False, description="Whether episode is complete")
    cumulative_reward: float = Field(0.0, description="Total reward accrued so far")
    last_action_signature: str = Field("", description="Signature of previous action for loop detection")
    repeated_invalid_actions: int = Field(0, description="Count of repeated invalid actions")
