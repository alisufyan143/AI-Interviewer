from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON
from app.database import Base
from app.models.interview import generate_uuid, utcnow


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    interview_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interviews.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    concerns: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    recommendation: Mapped[str] = mapped_column(
        String(20), nullable=False, default="hold"
    )  # strong_proceed | proceed | hold | reject
    recording_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # Relationships
    interview: Mapped["Interview"] = relationship(back_populates="report")
    assessment_scores: Mapped[list["AssessmentScore"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "overall_score": self.overall_score,
            "summary": self.summary,
            "strengths": self.strengths,
            "concerns": self.concerns,
            "recommendation": self.recommendation,
            "recording_path": self.recording_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "assessment_scores": [s.to_dict() for s in self.assessment_scores]
            if self.assessment_scores
            else [],
        }


# Avoid circular import
from app.models.interview import Interview  # noqa: E402, F811


class AssessmentScore(Base):
    __tablename__ = "assessment_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_reports.id", ondelete="CASCADE"), nullable=False
    )
    point_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    report: Mapped["InterviewReport"] = relationship(back_populates="assessment_scores")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "point_name": self.point_name,
            "score": self.score,
            "max_score": self.max_score,
            "evidence": self.evidence,
            "reasoning": self.reasoning,
        }
