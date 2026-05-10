import json
import logging
from typing import List, Dict
from google import genai
from google.genai import types
from app.config import settings
from app.services.model_manager import model_manager
from app.models.interview import Interview, InterviewMessage
from app.models.report import InterviewReport, AssessmentScore

logger = logging.getLogger(__name__)

class ScoringEngine:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = model_manager.get_model("scoring")

    async def generate_report(self, interview: Interview, messages: List[InterviewMessage]) -> Dict:
        """Analyze the interview transcript and generate a structured report using Gemini 3.1 Pro."""
        
        # Prepare context
        transcript = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in messages])
        jd = interview.job_description
        resume = interview.resume_text or "No resume provided."
        points = interview.assessment_points
        
        points_json = json.dumps(points, indent=2)

        prompt = f"""You are a senior recruitment analyst. Analyze the following interview transcript and generate a detailed assessment report.

JOB DESCRIPTION:
{jd}

CANDIDATE RESUME:
{resume}

INTERVIEW TRANSCRIPT:
{transcript}

ASSESSMENT CRITERIA:
{points_json}

INSTRUCTIONS:
1. Score each assessment criterion on a scale of 0 to 10.
2. Provide a brief reasoning and specific evidence from the transcript for each score.
3. Calculate an overall score (0-100) based on weighted averages of the individual scores.
4. Write a concise executive summary of the candidate's performance.
5. Identify key strengths and potential concerns.
6. Provide a recommendation: strong_proceed, proceed, hold, or reject.

OUTPUT FORMAT (Strict JSON):
{{
  "overall_score": 85,
  "summary": "...",
  "strengths": ["...", "..."],
  "concerns": ["...", "..."],
  "recommendation": "proceed",
  "assessment_scores": [
    {{
      "point_name": "Technical Skills",
      "score": 8,
      "max_score": 10,
      "evidence": "Candidate explained React hooks clearly...",
      "reasoning": "Strong fundamental knowledge but missed some advanced patterns."
    }}
  ]
}}
"""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            report_data = json.loads(response.text)
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating scoring report: {e}")
            raise
