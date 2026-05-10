import os
import json
import logging
import asyncio
import io
from typing import List, Dict, Optional, Tuple
from google import genai
from google.genai import types
import assemblyai as aai
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from app.config import settings
from app.models.interview import Interview, InterviewMessage
from app.utils.prompts import build_interview_system_prompt

logger = logging.getLogger(__name__)

class InterviewService:
    def __init__(self):
        # 1. Initialize Clients
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.eleven_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
        
        # 2. Configuration
        self.gemini_model = settings.GEMINI_LIVE_MODEL
        self.assembly_config = aai.TranscriptionConfig(speech_models=[settings.ASSEMBLYAI_MODEL])
        self.eleven_model = settings.ELEVENLABS_MODEL
        
        # 3. Voice Management
        self._sarah_voice_id = None

    async def _get_voice_id(self) -> str:
        """Find Sarah's voice ID with zero assumptions about SDK return types."""
        if self._sarah_voice_id:
            return self._sarah_voice_id
            
        try:
            # ElevenLabs SDK can be inconsistent; fetch and handle multiple formats
            response = await asyncio.to_thread(self.eleven_client.voices.get_all)
            
            # If response is an object with a 'voices' attribute (some versions)
            voices_list = getattr(response, 'voices', response)
            
            # If it's a tuple (data, metadata), take the data
            if isinstance(voices_list, tuple):
                voices_list = voices_list[0]

            for v in voices_list:
                # Robust attribute access (check for object attr, then dict key, then tuple)
                name = getattr(v, 'name', None) or (v.get('name') if isinstance(v, dict) else None)
                vid = getattr(v, 'voice_id', None) or (v.get('voice_id') if isinstance(v, dict) else None)
                
                if name and vid and name in ["Alice", "Aria", "Charlotte", "Laura"]:
                    self._sarah_voice_id = vid
                    return vid
            
            # Final fallback: take the first valid voice found
            if voices_list and len(voices_list) > 0:
                first = voices_list[0]
                self._sarah_voice_id = getattr(first, 'voice_id', None) or (first.get('voice_id') if isinstance(first, dict) else None)
                return self._sarah_voice_id
                
        except Exception as e:
            logger.error(f"Failed to fetch ElevenLabs voices: {e}")
        return None

    async def _generate_audio(self, text: str) -> bytes:
        """Generate audio with safety fallback."""
        voice_id = await self._get_voice_id()
        if not voice_id:
            logger.warning("No voice ID found after robust search")
            return b""
            
        try:
            logger.info(f"Generating ElevenLabs audio for: {text[:50]}...")
            response = await asyncio.to_thread(
                self.eleven_client.text_to_speech.convert,
                voice_id=voice_id,
                output_format="mp3_22050_32",
                text=text,
                model_id=self.eleven_model,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.8,
                )
            )
            return b"".join(list(response))
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {e}")
            return b""

    async def get_initial_greeting(self, interview: Interview) -> Tuple[str, bytes]:
        """Generate greeting with system_instruction."""
        system_prompt = build_interview_system_prompt(interview.to_dict())
        system_prompt += "\n\n[CRITICAL] Be Very Concise and Professional. No Yapping."
        
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[
                    types.Content(role="user", parts=[types.Part.from_text(text="Please introduce yourself and start the interview.")])
                ],
                config=types.GenerateContentConfig(system_instruction=system_prompt)
            )
            text = response.text.strip()
            audio_bytes = await self._generate_audio(text)
            return text, audio_bytes
        except Exception as e:
            logger.error(f"Greeting failed: {e}")
            fallback_text = "Hello, I'm Sarah from Right Recruit. Let's begin."
            return fallback_text, await self._generate_audio(fallback_text)

    async def process_user_turn(self, interview: Interview, messages: List[InterviewMessage], user_audio_path: str) -> Tuple[str, str, bytes]:
        """Full STT -> LLM -> TTS pipeline."""
        try:
            transcriber = aai.Transcriber(config=self.assembly_config)
            transcript = await asyncio.to_thread(transcriber.transcribe, user_audio_path)
            user_text = transcript.text or "Audio received."
        except Exception as e:
            logger.error(f"STT failed: {e}")
            user_text = "Audio received."

        system_prompt = build_interview_system_prompt(interview.to_dict())
        system_prompt += "\n\n[CRITICAL] Be Very Concise and Professional. No Yapping."
        
        history = []
        for msg in messages:
            role = "user" if msg.role == "candidate" else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.content)]))
        
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[*history, types.Content(role="user", parts=[types.Part.from_text(text=user_text)])],
                config=types.GenerateContentConfig(system_instruction=system_prompt)
            )
            sarah_text = response.text.strip()
        except Exception as e:
            logger.error(f"LLM failed: {e}")
            sarah_text = "I'm sorry, I missed that. Could you repeat?"

        audio_bytes = await self._generate_audio(sarah_text)
        return user_text, sarah_text, audio_bytes
