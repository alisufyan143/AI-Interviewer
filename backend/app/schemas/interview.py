from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AssessmentPointSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Assessment point name")
    description: str = Field("", max_length=1000, description="What to assess")
    weight: int = Field(3, ge=1, le=5, description="Importance weight 1-5")


class InterviewCreateRequest(BaseModel):
    job_title: str = Field(..., min_length=1, max_length=255)
    job_description: str = Field(..., min_length=10)
    candidate_name: str = Field(..., min_length=1, max_length=255)
    candidate_email: Optional[str] = Field(None, max_length=255)
    assessment_points: list[AssessmentPointSchema] = Field(..., min_length=3, max_length=10)
    max_duration_minutes: int = Field(15, ge=5, le=30)


class InterviewResponse(BaseModel):
    id: str
    job_title: str
    job_description: str
    candidate_name: str
    candidate_email: Optional[str]
    resume_text: Optional[str]
    resume_parsed_json: Optional[dict]
    resume_path: Optional[str]
    assessment_points: list[dict | str]
    interview_token: str
    status: str
    max_duration_minutes: int
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]
    interview_link: Optional[str] = None
    report: Optional[dict] = None


class InterviewListResponse(BaseModel):
    interviews: list[InterviewResponse]
    total: int


class DashboardStatsResponse(BaseModel):
    total_interviews: int
    completed: int
    pending: int
    in_progress: int
    average_score: Optional[float]


class MessageResponse(BaseModel):
    id: str
    interview_id: str
    role: str
    content: str
    timestamp_seconds: float
    created_at: Optional[str]
