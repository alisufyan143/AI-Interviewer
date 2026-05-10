export interface AssessmentPoint {
  name: string;
  description: string;
  weight: number;
}

export interface Interview {
  id: string;
  job_title: string;
  job_description: string;
  candidate_name: string;
  candidate_email: string | null;
  resume_text: string | null;
  resume_parsed_json: Record<string, unknown> | null;
  resume_path: string | null;
  assessment_points: AssessmentPoint[];
  interview_token: string;
  status: 'pending' | 'in_progress' | 'completed' | 'expired';
  max_duration_minutes: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  interview_link: string | null;
  report: InterviewReport | null;
  messages?: InterviewMessage[];
}

export interface InterviewMessage {
  id: string;
  interview_id: string;
  role: 'ai' | 'candidate';
  content: string;
  timestamp_seconds: number;
  created_at: string | null;
}

export interface AssessmentScore {
  id: string;
  report_id: string;
  point_name: string;
  score: number;
  max_score: number;
  evidence: string | null;
  reasoning: string | null;
}

export interface InterviewReport {
  id: string;
  interview_id: string;
  overall_score: number;
  summary: string | null;
  strengths: string[];
  concerns: string[];
  recommendation: 'strong_proceed' | 'proceed' | 'hold' | 'reject';
  recording_path: string | null;
  created_at: string | null;
  assessment_scores: AssessmentScore[];
}

export interface DashboardStats {
  total_interviews: number;
  completed: number;
  pending: number;
  in_progress: number;
  average_score: number | null;
}
