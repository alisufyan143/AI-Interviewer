import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_token() -> str:
    """Generate a URL-safe token for interview links."""
    return uuid.uuid4().hex[:16]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assessment_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    interview_token: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False, default=generate_token
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    max_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # Relationships
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="InterviewMessage.timestamp_seconds"
    )
    report: Mapped["InterviewReport | None"] = relationship(
        "InterviewReport", back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_title": self.job_title,
            "job_description": self.job_description,
            "candidate_name": self.candidate_name,
            "candidate_email": self.candidate_email,
            "resume_text": self.resume_text,
            "resume_parsed_json": self.resume_parsed_json,
            "resume_path": self.resume_path,
            "assessment_points": self.assessment_points,
            "interview_token": self.interview_token,
            "status": self.status,
            "max_duration_minutes": self.max_duration_minutes,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Import here to avoid circular import in relationship definition
from app.models.report import InterviewReport  # noqa: E402, F811


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    interview_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "ai" or "candidate"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # Relationships
    interview: Mapped["Interview"] = relationship(back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "role": self.role,
            "content": self.content,
            "timestamp_seconds": self.timestamp_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
