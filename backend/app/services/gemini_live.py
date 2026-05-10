import asyncio
import logging
from typing import Callable, Optional
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

from app.services.model_manager import model_manager

class GeminiLiveSession:
    def __init__(self, system_prompt: str):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = model_manager.get_model("live")
        self.system_prompt = system_prompt
        self.ai_session = None
        self.on_audio_callback = None
        self.on_transcript_callback = None
        self.on_interrupted_callback = None
        self.on_turn_complete_callback = None
        # Transcript buffers — accumulate fragments, emit on turn_complete
        self._ai_buffer = []
        self._candidate_buffer = []
        # Connection state tracking
        self._connected = False
        self._error: Optional[str] = None
        # Manual VAD activity state
        self._activity_active = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    async def connect(self, 
                      on_audio: Callable[[bytes], None], 
                      on_transcript: Callable[[str, str], None],
                      on_interrupted: Optional[Callable[[], None]] = None,
                      on_turn_complete: Optional[Callable[[], None]] = None):
        """Connect to Gemini Live API with audio + transcription."""
        self.on_audio_callback = on_audio
        self.on_transcript_callback = on_transcript
        self.on_interrupted_callback = on_interrupted
        self.on_turn_complete_callback = on_turn_complete

        config = {
            "system_instruction": {"parts": [{"text": self.system_prompt}]},
            "response_modalities": ["AUDIO"],
            "output_audio_transcription": {},
            "input_audio_transcription": {},
            "realtime_input_config": {
                "automatic_activity_detection": {
                    "disabled": True
                }
            },
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Puck"
                    }
                }
            }
        }

        try:
            async with self.client.aio.live.connect(model=self.model_id, config=config) as session:
                self.ai_session = session
                self._connected = True
                logger.info(f"Connected to Gemini Live: {self.model_id}")
                
                # Trigger the AI to greet the candidate immediately
                await session.send_client_content(
                    turns=[{"role": "user", "parts": [{"text": "The candidate has just joined the interview room. Begin the interview now by greeting them warmly and introducing yourself."}]}],
                    turn_complete=True
                )
                
                async for message in session.receive():
                    if not message.server_content:
                        continue
                    content = message.server_content
                    
                    # --- AI Audio ---
                    if content.model_turn and content.model_turn.parts:
                        # When AI starts speaking, flush any pending candidate buffer
                        self._flush_candidate_buffer()
                        
                        for part in content.model_turn.parts:
                            if part.inline_data and self.on_audio_callback:
                                self.on_audio_callback(part.inline_data.data)
                    
                    # --- AI transcript (word-by-word from output_audio_transcription) ---
                    if hasattr(content, 'output_transcription') and content.output_transcription:
                        text = getattr(content.output_transcription, 'text', None)
                        if text:
                            self._ai_buffer.append(text)
                    
                    # --- Candidate transcript (from input_audio_transcription) ---
                    if hasattr(content, 'input_transcription') and content.input_transcription:
                        text = getattr(content.input_transcription, 'text', None)
                        if text:
                            self._candidate_buffer.append(text)
                    
                    # --- Turn complete: flush AI buffer, then open mic for candidate ---
                    if hasattr(content, 'turn_complete') and content.turn_complete:
                        self._flush_ai_buffer()
                        # AUTO-START activity so Gemini listens for the candidate
                        await self._start_activity()
                        if self.on_turn_complete_callback:
                            self.on_turn_complete_callback()
                    
                    # --- Interruption (guarded access) ---
                    if hasattr(content, 'interrupted') and content.interrupted:
                        self._ai_buffer.clear()
                        if self.on_interrupted_callback:
                            self.on_interrupted_callback()
                    
        except Exception as e:
            # Flush any remaining buffers
            self._flush_ai_buffer()
            self._flush_candidate_buffer()
            if "1000" in str(e):
                logger.info("Gemini Live session closed normally.")
            else:
                self._error = str(e)
                logger.error(f"Gemini Live error: {e}")
                raise
        finally:
            self._connected = False

    def _flush_ai_buffer(self):
        """Emit accumulated AI transcript as a single message."""
        if self._ai_buffer and self.on_transcript_callback:
            full_text = "".join(self._ai_buffer).strip()
            if full_text:
                self.on_transcript_callback("ai", full_text)
        self._ai_buffer.clear()

    def _flush_candidate_buffer(self):
        """Emit accumulated candidate transcript as a single message."""
        if self._candidate_buffer and self.on_transcript_callback:
            full_text = "".join(self._candidate_buffer).strip()
            if full_text:
                self.on_transcript_callback("candidate", full_text)
        self._candidate_buffer.clear()

    async def _start_activity(self):
        """Send activity_start signal — tells Gemini the candidate is about to speak.
        Required when automatic_activity_detection is disabled."""
        if self.ai_session and self._connected and not self._activity_active:
            try:
                await self.ai_session.send_realtime_input(
                    activity_start=types.ActivityStart()
                )
                self._activity_active = True
                logger.info("Sent activity_start to Gemini")
            except Exception as e:
                logger.error(f"activity_start error: {e}")

    async def _end_activity(self):
        """Send activity_end signal — tells Gemini the candidate has stopped speaking.
        Required when automatic_activity_detection is disabled."""
        if self.ai_session and self._connected and self._activity_active:
            try:
                self._flush_candidate_buffer()
                await self.ai_session.send_realtime_input(
                    activity_end=types.ActivityEnd()
                )
                self._activity_active = False
                logger.info("Sent activity_end to Gemini")
            except Exception as e:
                logger.error(f"activity_end error: {e}")

    async def send_audio(self, audio_bytes: bytes):
        if self.ai_session and self._connected:
            try:
                await self.ai_session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                logger.error(f"send_audio error: {e}")

    async def signal_turn_complete(self):
        """Candidate clicked 'Done' — send activity_end to trigger Gemini response."""
        await self._end_activity()

    async def close(self):
        self._connected = False
        if self.ai_session:
            try:
                await self.ai_session.close()
            except Exception:
                pass
            self.ai_session = None
