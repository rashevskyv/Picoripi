"""Pydantic data models for Picoripi Companion API."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    token: str = Field(..., description="Access token or PIN")


class LoginResponse(BaseModel):
    success: bool
    token: str
    message: str = ""


class ProjectSummary(BaseModel):
    id: str
    name: str
    updated_at: str
    total_terms: int = 0
    confirmed_terms: int = 0
    needs_review_terms: int = 0


class SyncPushRequest(BaseModel):
    project_name: str = Field(..., min_length=1)
    glossary: List[Dict[str, Any]] = Field(default_factory=list)
    occurrences: Optional[Dict[str, List[Dict[str, Any]]]] = None
    metadata: Optional[Dict[str, Any]] = None


class SyncPushResponse(BaseModel):
    success: bool
    message: str
    total_terms: int
    updated_at: str


class SyncPullResponse(BaseModel):
    project_name: str
    glossary: List[Dict[str, Any]]
    updated_at: str
    total_terms: int


class GlossaryEntryUpdate(BaseModel):
    original: str = Field(..., min_length=1)
    translation: Optional[str] = None
    status: Optional[str] = None
    user_notes: Optional[str] = None
    notes: Optional[str] = None
    section: Optional[str] = None
    updated_at: Optional[str] = None


class GlossaryListResponse(BaseModel):
    project_name: str
    total: int
    categories: List[str]
    category_counts: Dict[str, int]
    needs_review_count: int
    confirmed_count: int
    entries: List[Dict[str, Any]]


class TermDetailResponse(BaseModel):
    entry: Dict[str, Any]
    occurrences: List[Dict[str, Any]] = Field(default_factory=list)
