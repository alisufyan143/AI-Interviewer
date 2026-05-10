# Right Recruit - AI Interviewer

An automated, real-time AI interviewing platform designed to streamline initial candidate screening. Right Recruit utilizes advanced speech-to-text, large language models, and text-to-speech technologies to conduct dynamic, turn-based technical and behavioral interviews.

## 🚀 Features

- **Real-Time Voice Interviews**: Conduct seamless, low-latency voice interviews with candidates.
- **Dynamic Turn-Based Engine**: Robust WebSocket architecture ensuring synchronized turns between the candidate and the AI.
- **Perfect Audio Sync**: Frontend utilizes the Web Audio API to flawlessly synchronize the AI's speech with visual waveforms.
- **Automated Resume Parsing**: Extract key candidate information from uploaded resumes (PDF, DOCX, etc.).
- **Smart Scoring & Assessment**: Automatically generate comprehensive reports, scoring the candidate across customizable assessment points.
- **"No-Fail" Architecture**: Built-in fallbacks and state management for API rate limits and network interruptions.

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: SQLite (via SQLAlchemy & aiosqlite)
- **Speech-to-Text (STT)**: AssemblyAI (`universal-3-pro`)
- **Large Language Model (LLM)**: Google Gemini (`gemini-flash-latest`)
- **Text-to-Speech (TTS)**: ElevenLabs (`eleven_flash_v2_5`)

### Frontend
- **Framework**: Next.js 16 (React)
- **Language**: TypeScript
- **Styling**: Tailwind CSS / Vanilla CSS
- **Audio Processing**: Web Audio API & MediaRecorder API

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- Node.js (v18+)
- Python (v3.10+)
- API Keys for:
  - Google Gemini
  - AssemblyAI
  - ElevenLabs

## ⚙️ Local Development Setup

### 1. Backend Setup

```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory with your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

Start the FastAPI server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

Start the Next.js development server:
```bash
npm run dev
```

The application will be available at `http://localhost:3000`.

## 🏗️ Architecture Flow

1. **Initialization**: Candidate joins via a secure token. The backend sends the initial AI greeting.
2. **Recording**: Frontend streams candidate audio chunks to the backend via WebSockets.
3. **Processing**:
   - Audio is transcribed via AssemblyAI.
   - Transcript and interview history are processed by Gemini to generate the next question/response.
   - Text response is synthesized into speech using ElevenLabs.
4. **Playback**: Frontend receives binary audio packets, decodes them via `AudioContext`, and visualizes the waveform.
5. **Completion**: Upon finishing the interview, the `ScoringEngine` automatically evaluates the transcript against predefined assessment points and saves the final report.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License.
