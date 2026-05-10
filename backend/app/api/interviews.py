import os
import shutil
import logging
import asyncio
import base64
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models.interview import Interview, InterviewMessage
from app.models.report import InterviewReport, AssessmentScore
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewResponse,
    InterviewListResponse,
    DashboardStatsResponse,
)
from app.config import settings
from app.services.resume_parser import parse_resume
from app.services.interview_service import InterviewService
from app.services.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])

# SINGLETON SERVICE: Initialize once at module level to avoid client creation overhead
interview_service = InterviewService()


def _interview_to_response(interview: Interview, report=None, base_url: str = "http://localhost:3000") -> dict:
    """Convert an Interview model to a response dict with interview link."""
    data = interview.to_dict()
    data["interview_link"] = f"{base_url}/room/{interview.interview_token}"
    if report is not None:
        data["report"] = report.to_dict()
    else:
        data["report"] = None
    return data

@router.post("/parse-resume")
async def upload_and_parse_resume(file: UploadFile = File(...)):
    """Standalone endpoint to parse a resume and return structured data."""
    ext = Path(file.filename).suffix.lower()
    if ext not in [".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use PDF, DOCX, PNG, or JPG.",
        )

    temp_path = settings.UPLOADS_DIR / f"temp_{_uuid.uuid4().hex}{ext}"
    try:
        content = await file.read()
        await asyncio.to_thread(temp_path.write_bytes, content)
        parsed = await parse_resume(temp_path)
        return parsed
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    total = await db.scalar(select(func.count(Interview.id)))
    completed = await db.scalar(
        select(func.count(Interview.id)).where(Interview.status == "completed")
    )
    pending = await db.scalar(
        select(func.count(Interview.id)).where(Interview.status == "pending")
    )
    in_progress = await db.scalar(
        select(func.count(Interview.id)).where(Interview.status == "in_progress")
    )
    avg_score = await db.scalar(
        select(func.avg(InterviewReport.overall_score))
    )

    return DashboardStatsResponse(
        total_interviews=total or 0,
        completed=completed or 0,
        pending=pending or 0,
        in_progress=in_progress or 0,
        average_score=round(avg_score, 1) if avg_score else None,
    )


@router.get("", response_model=InterviewListResponse)
async def list_interviews(
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all interviews with optional filtering."""
    query = select(Interview).order_by(desc(Interview.created_at))

    if status and status != "all":
        query = query.where(Interview.status == status)
    if search:
        query = query.where(
            Interview.candidate_name.ilike(f"%{search}%")
            | Interview.job_title.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    interviews = result.scalars().all()

    interview_ids = [i.id for i in interviews]
    if interview_ids:
        reports_result = await db.execute(
            select(InterviewReport)
            .where(InterviewReport.interview_id.in_(interview_ids))
            .options(selectinload(InterviewReport.assessment_scores))
        )
        reports_map = {r.interview_id: r for r in reports_result.scalars().all()}
    else:
        reports_map = {}

    return InterviewListResponse(
        interviews=[
            InterviewResponse(**_interview_to_response(i, report=reports_map.get(i.id))) for i in interviews
        ],
        total=total or 0,
    )


@router.get("/{interview_id}")
async def get_interview(interview_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single interview with its report and messages."""
    interview = await db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    report_result = await db.execute(
        select(InterviewReport)
        .where(InterviewReport.interview_id == interview_id)
        .options(selectinload(InterviewReport.assessment_scores))
    )
    report = report_result.scalar_one_or_none()

    data = _interview_to_response(interview, report=report)

    messages_result = await db.execute(
        select(InterviewMessage)
        .where(InterviewMessage.interview_id == interview_id)
        .order_by(InterviewMessage.timestamp_seconds)
    )
    data["messages"] = [m.to_dict() for m in messages_result.scalars().all()]

    return data


@router.get("/token/{token}")
async def get_interview_by_token(token: str, db: AsyncSession = Depends(get_db)):
    """Get interview by its public token (used by candidate room)."""
    result = await db.execute(
        select(Interview).where(Interview.interview_token == token)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {
        "id": interview.id,
        "job_title": interview.job_title,
        "candidate_name": interview.candidate_name,
        "status": interview.status,
        "max_duration_minutes": interview.max_duration_minutes,
    }


@router.post("", status_code=201)
async def create_interview(
    job_title: str = Form(...),
    job_description: str = Form(...),
    candidate_name: str = Form(...),
    candidate_email: Optional[str] = Form(None),
    assessment_points: str = Form(...),
    max_duration_minutes: int = Form(15),
    resume: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Create a new interview with optional resume upload."""
    import json

    try:
        points = json.loads(assessment_points)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid assessment_points JSON")

    resume_text = None
    resume_parsed_json = None
    resume_path = None

    if resume:
        ext = Path(resume.filename).suffix.lower()
        safe_filename = f"{_uuid.uuid4().hex[:16]}{ext}"
        file_path = settings.UPLOADS_DIR / safe_filename
        
        content = await resume.read()
        await asyncio.to_thread(file_path.write_bytes, content)
        resume_path = str(file_path)

        try:
            parsed = await parse_resume(file_path)
            resume_text = parsed.get("raw_text", "")
            resume_parsed_json = parsed
        except Exception as e:
            logger.warning(f"Resume parsing failed: {e}")
            resume_text = f"[Resume uploaded but parsing failed]"

    interview = Interview(
        job_title=job_title,
        job_description=job_description,
        candidate_name=candidate_name,
        candidate_email=candidate_email if candidate_email else None,
        resume_text=resume_text,
        resume_parsed_json=resume_parsed_json,
        resume_path=resume_path,
        assessment_points=points,
        max_duration_minutes=max_duration_minutes,
    )

    db.add(interview)
    await db.commit()
    await db.refresh(interview)

    return _interview_to_response(interview, report=None)


@router.delete("/{interview_id}")
async def delete_interview(interview_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an interview and its associated files."""
    interview = await db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview.resume_path and os.path.exists(interview.resume_path):
        os.remove(interview.resume_path)

    report_result = await db.execute(
        select(InterviewReport).where(InterviewReport.interview_id == interview_id)
    )
    report = report_result.scalar_one_or_none()
    if report and report.recording_path and os.path.exists(report.recording_path):
        os.remove(report.recording_path)

    await db.delete(interview)
    await db.commit()

    return {"message": "Interview deleted successfully"}


@router.post("/{interview_id}/score")
async def trigger_scoring(interview_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger AI scoring for a completed interview."""
    interview = await db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    existing_report_result = await db.execute(
        select(InterviewReport).where(InterviewReport.interview_id == interview_id)
    )
    existing_report = existing_report_result.scalar_one_or_none()
    if existing_report:
        await db.delete(existing_report)
        await db.flush()
    
    messages_result = await db.execute(
        select(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
    )
    messages = list(messages_result.scalars().all())
    
    if not messages:
        raise HTTPException(status_code=400, detail="No transcript available for scoring")
    
    engine = ScoringEngine()
    try:
        report_data = await engine.generate_report(interview, messages)
        
        report = InterviewReport(
            interview_id=interview.id,
            overall_score=report_data.get("overall_score", 0),
            summary=report_data.get("summary", ""),
            strengths=report_data.get("strengths", []),
            concerns=report_data.get("concerns", []),
            recommendation=report_data.get("recommendation", "hold")
        )
        db.add(report)
        await db.flush()
        
        for s in report_data.get("assessment_scores", []):
            score = AssessmentScore(
                report_id=report.id,
                point_name=s.get("point_name", ""),
                score=s.get("score", 0),
                max_score=s.get("max_score", 10),
                evidence=s.get("evidence", ""),
                reasoning=s.get("reasoning", "")
            )
            db.add(score)
        
        interview.status = "completed"
        await db.commit()
        return {"message": "Scoring completed", "report_id": report.id}
        
    except Exception as e:
        await db.rollback()
        logger.exception(f"Scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/token/{token}/start")
async def start_discrete_interview(token: str, db: AsyncSession = Depends(get_db)):
    """Initialize a discrete interview and get Sarah's first greeting."""
    result = await db.execute(select(Interview).where(Interview.interview_token == token))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # IDEMPOTENCY Check
    msg_result = await db.execute(
        select(InterviewMessage).where(InterviewMessage.interview_id == interview.id, InterviewMessage.role == "ai").limit(1)
    )
    existing_msg = msg_result.scalar_one_or_none()

    if existing_msg:
        text = existing_msg.content
        audio_bytes = await interview_service._generate_audio(text)
    else:
        # FIX: Inject a hidden user-role start message to satisfy Gemini's history logic
        start_msg = InterviewMessage(
            interview_id=interview.id,
            role="candidate",
            content="[Interview Started]",
            timestamp_seconds=0.0
        )
        db.add(start_msg)
        await db.flush()

        # Generate Sarah's response to the start signal
        text, audio_bytes = await interview_service.get_initial_greeting(interview)
        ai_msg = InterviewMessage(
            interview_id=interview.id,
            role="ai",
            content=text,
            timestamp_seconds=0.1
        )
        db.add(ai_msg)
    
    if interview.status == "pending":
        interview.status = "in_progress"
        interview.started_at = datetime.now()
    
    await db.commit()
    
    return {
        "text": text,
        "audio_base64": base64.b64encode(audio_bytes).decode('utf-8')
    }


@router.post("/token/{token}/respond")
async def respond_to_candidate(
    token: str, 
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Process candidate's audio message and return Sarah's response."""
    result = await db.execute(select(Interview).where(Interview.interview_token == token))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    temp_filename = f"user_{_uuid.uuid4().hex}.webm"
    temp_path = settings.RECORDINGS_DIR / temp_filename
    
    try:
        content = await audio.read()
        await asyncio.to_thread(temp_path.write_bytes, content)
    
        messages_result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview.id)
            .order_by(InterviewMessage.timestamp_seconds)
        )
        history = list(messages_result.scalars().all())
        
        user_text, sarah_text, sarah_audio_bytes = await interview_service.process_user_turn(interview, history, str(temp_path))
        
        start_time = interview.started_at or datetime.now()
        ts = (datetime.now() - start_time).total_seconds()
        
        db.add(InterviewMessage(interview_id=interview.id, role="candidate", content=user_text, timestamp_seconds=ts))
        db.add(InterviewMessage(interview_id=interview.id, role="ai", content=sarah_text, timestamp_seconds=ts + 0.5))
        
        await db.commit()
        
        return {
            "user_text": user_text,
            "ai_text": sarah_text,
            "audio_base64": base64.b64encode(sarah_audio_bytes).decode('utf-8')
        }
    finally:
        if temp_path.exists():
            os.remove(temp_path)

async def _auto_score(interview_id: str):
    """Score the interview immediately after it ends."""
    from app.services.scoring_engine import ScoringEngine
    from app.models.report import InterviewReport, AssessmentScore
    from app.database import async_session
    from sqlalchemy import select
    from app.models.interview import Interview, InterviewMessage
    
    async with async_session() as db:
        iv = await db.get(Interview, interview_id)
        msg_result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.timestamp_seconds)
        )
        messages = list(msg_result.scalars().all())
        
        if not iv or not messages:
            return
        
        try:
            engine = ScoringEngine()
            report_data = await engine.generate_report(iv, messages)
            
            report = InterviewReport(
                interview_id=interview_id,
                overall_score=report_data.get("overall_score", 0),
                summary=report_data.get("summary", ""),
                strengths=report_data.get("strengths", []),
                concerns=report_data.get("concerns", []),
                recommendation=report_data.get("recommendation", "hold"),
            )
            db.add(report)
            await db.flush()
            
            for s in report_data.get("assessment_scores", []):
                db.add(AssessmentScore(
                    report_id=report.id,
                    point_name=s.get("point_name", ""),
                    score=s.get("score", 0),
                    max_score=s.get("max_score", 10),
                    evidence=s.get("evidence", ""),
                    reasoning=s.get("reasoning", ""),
                ))
            
            await db.commit()
        except Exception as e:
            print(f"Scoring failed: {e}")
