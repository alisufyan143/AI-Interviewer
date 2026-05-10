import asyncio
import json
import logging
import time
import wave
import io
import os
import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google import genai
from google.genai import types
import assemblyai as aai
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from app.database import get_db, async_session
from app.models.interview import Interview, InterviewMessage
from app.models.report import InterviewReport, AssessmentScore
from app.utils.prompts import build_interview_system_prompt
from app.config import settings

logger = logging.getLogger(__name__)
# Force logger to INFO for debugging
logging.basicConfig(level=logging.INFO)
router = APIRouter(tags=["websocket"])

# --- SHARED CLIENTS ---
aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
eleven_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

async def _auto_score_self_contained(interview_id: str):
    """Scoring logic moved here to avoid any import/circular issues."""
    logger.info(f"[DEBUG] [SCORING] Starting auto-score for {interview_id}")
    from app.services.scoring_engine import ScoringEngine
    try:
        async with async_session() as db:
            iv = await db.get(Interview, interview_id)
            msg_result = await db.execute(
                select(InterviewMessage)
                .where(InterviewMessage.interview_id == interview_id)
                .order_by(InterviewMessage.timestamp_seconds)
            )
            messages = list(msg_result.scalars().all())
            
            if not iv or not messages:
                logger.warning(f"[DEBUG] [SCORING] No data for {interview_id}")
                return
            
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
            logger.info(f"[DEBUG] [SCORING] Successfully generated report for {interview_id}")
    except Exception as e:
        logger.error(f"[DEBUG] [SCORING] Scoring failed: {e}")

async def get_sarah_voice_id():
    logger.info("[DEBUG] [TTS] Fetching voices from ElevenLabs...")
    try:
        voices = await asyncio.to_thread(eleven_client.voices.get_all)
        v_list = getattr(voices, 'voices', voices)
        if isinstance(v_list, tuple): v_list = v_list[0]
        
        for v in v_list:
            name = getattr(v, 'name', None) or (v.get('name') if isinstance(v, dict) else None)
            vid = getattr(v, 'voice_id', None) or (v.get('voice_id') if isinstance(v, dict) else None)
            # Prioritize female voices
            if name in ["Alice", "Aria", "Charlotte", "Laura", "Sarah", "Rachel"]:
                logger.info(f"[DEBUG] [TTS] Found Sarah voice: {name} ({vid})")
                return vid
    except Exception as e:
        logger.error(f"[DEBUG] [TTS] Voice fetch failed: {e}")
    
    return "21m00Tcm4TlvDq8ikWAM" # Confirmed female Rachel voice

@router.websocket("/ws/interview/{token}")
async def interview_websocket(websocket: WebSocket, token: str):
    logger.info(f"[DEBUG] [WS] Connection attempt with token: {token}")
    
    try:
        # 1. Setup & Auth
        async with async_session() as db:
            result = await db.execute(select(Interview).where(Interview.interview_token == token))
            interview = result.scalar_one_or_none()
            if not interview:
                logger.warning(f"[DEBUG] [WS] Token rejected: {token}")
                await websocket.close(code=4003)
                return
            
            interview_id = interview.id
            candidate_name = interview.candidate_name
            system_prompt = build_interview_system_prompt(interview.to_dict())
            system_prompt += "\n\n[CRITICAL] Be Very Concise and Professional. No Yapping."
            
            msg_result = await db.execute(
                select(InterviewMessage).where(InterviewMessage.interview_id == interview_id).order_by(InterviewMessage.timestamp_seconds)
            )
            history_msgs = list(msg_result.scalars().all())
            
        await websocket.accept()
        logger.info(f"[DEBUG] [WS] Connection accepted for {candidate_name}")

        # Update Status
        async with async_session() as db:
            iv = await db.get(Interview, interview_id)
            if iv:
                iv.status = "in_progress"
                iv.started_at = datetime.now()
                await db.commit()

        # State & History
        start_time = time.time()
        history = []
        for m in history_msgs:
            role = "user" if m.role == "candidate" else "model"
            if m.content == "[Interview Started]": continue
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))

        voice_id = await get_sarah_voice_id()
        
        async def save_msg(role: str, text: str):
            async with async_session() as db:
                db.add(InterviewMessage(
                    interview_id=interview_id,
                    role=role,
                    content=text,
                    timestamp_seconds=time.time() - start_time
                ))
                await db.commit()

        # Initial Greeting
        if not history:
            logger.info("[DEBUG] [LLM] Generating initial greeting...")
            response = await genai_client.aio.models.generate_content(
                model=settings.GEMINI_LIVE_MODEL,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text="Introduce yourself and start the interview.")])],
                config=types.GenerateContentConfig(system_instruction=system_prompt)
            )
            sarah_text = response.text.strip()
            logger.info(f"[DEBUG] [LLM] Response: {sarah_text}")
            
            await websocket.send_text(json.dumps({"type": "transcript", "role": "ai", "text": sarah_text}))
            await save_msg("ai", sarah_text)
            history.append(types.Content(role="model", parts=[types.Part.from_text(text=sarah_text)]))
            
            audio_bytes_gen = await asyncio.to_thread(
                eleven_client.text_to_speech.convert,
                voice_id=voice_id, text=sarah_text, model_id="eleven_flash_v2_5",
                voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8)
            )
            audio_bytes = b"".join(list(audio_bytes_gen))
            await websocket.send_bytes(audio_bytes)
            await websocket.send_text(json.dumps({"type": "turn_complete"}))

        # LOOP
        audio_buffer = io.BytesIO()
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                audio_buffer.write(message["bytes"])
            elif "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "turn_done":
                    temp_file = f"temp_{uuid.uuid4().hex}.webm"
                    with open(temp_file, "wb") as f:
                        f.write(audio_buffer.getvalue())
                    audio_buffer = io.BytesIO() 
                    
                    try:
                        transcriber = aai.Transcriber(config=aai.TranscriptionConfig(speech_models=["universal-3-pro"]))
                        transcript = await asyncio.to_thread(transcriber.transcribe, temp_file)
                        user_text = transcript.text or "Audio received."
                        logger.info(f"[DEBUG] [STT] Heard: {user_text}")
                    finally:
                        if os.path.exists(temp_file): os.remove(temp_file)

                    await websocket.send_text(json.dumps({"type": "transcript", "role": "candidate", "text": user_text}))
                    await save_msg("candidate", user_text)
                    
                    response = await genai_client.aio.models.generate_content(
                        model=settings.GEMINI_LIVE_MODEL,
                        contents=[*history, types.Content(role="user", parts=[types.Part.from_text(text=user_text)])],
                        config=types.GenerateContentConfig(system_instruction=system_prompt)
                    )
                    sarah_text = response.text.strip()
                    logger.info(f"[DEBUG] [LLM] Response: {sarah_text}")
                    history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))
                    history.append(types.Content(role="model", parts=[types.Part.from_text(text=sarah_text)]))

                    await websocket.send_text(json.dumps({"type": "transcript", "role": "ai", "text": sarah_text}))
                    await save_msg("ai", sarah_text)

                    audio_gen = await asyncio.to_thread(
                        eleven_client.text_to_speech.convert,
                        voice_id=voice_id, text=sarah_text, model_id="eleven_flash_v2_5",
                        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8)
                    )
                    await websocket.send_bytes(b"".join(list(audio_gen)))
                    await websocket.send_text(json.dumps({"type": "turn_complete"}))

                elif data.get("type") == "end_interview":
                    break

    except WebSocketDisconnect:
        logger.info("[DEBUG] [WS] Disconnected")
    except Exception as e:
        logger.error(f"[DEBUG] [WS] ERROR: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass
    finally:
        async with async_session() as db:
            iv = await db.get(Interview, interview_id)
            if iv:
                iv.status = "completed"
                iv.completed_at = datetime.now()
                await db.commit()
        asyncio.create_task(_auto_score_self_contained(interview_id))
