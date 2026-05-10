'use client';

import React, { useState, useEffect, useRef, useCallback, use } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

type Message = { role: 'ai' | 'candidate'; text: string };
type InterviewState = 'connecting' | 'welcome' | 'live' | 'ending' | 'error';

export default function InterviewRoom({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const router = useRouter();

  // --- State ---
  const [state, setState] = useState<InterviewState>('connecting');
  const [interview, setInterview] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [timeLeft, setTimeLeft] = useState(0);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Refs ---
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  
  const isAiSpeakingRef = useRef(false);
  const isProcessingRef = useRef(false);

  // --- Debug Logging ---
  const log = (area: string, msg: any) => {
    console.log(`[DEBUG] [${area}] ${new Date().toISOString().split('T')[1]} -`, msg);
  };

  // --- Initialization ---
  useEffect(() => {
    async function load() {
      log('INIT', 'Loading interview metadata...');
      try {
        const data = await api.getInterviewByToken(token);
        setInterview(data);
        setTimeLeft(data.max_duration_minutes * 60);
        setState('welcome');
        log('INIT', `Interview loaded for: ${data.candidate_name}`);
      } catch (err: any) {
        log('INIT', `Failed to load: ${err.message}`);
        setError(err.message || 'Failed to load interview');
        setState('error');
      }
    }
    load();
  }, [token]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- Audio Engine ---
  const initAudio = useCallback(() => {
    if (!audioContextRef.current) {
      log('AUDIO', 'Initializing AudioContext...');
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      audioContextRef.current = ctx;
      analyserRef.current = analyser;
    } else if (audioContextRef.current.state === 'suspended') {
      log('AUDIO', 'Resuming AudioContext...');
      audioContextRef.current.resume();
    }
  }, []);

  const playAudioBytes = useCallback(async (bytes: ArrayBuffer) => {
    log('AUDIO', `Received audio packet: ${bytes.byteLength} bytes`);
    initAudio();
    const ctx = audioContextRef.current!;
    try {
      log('AUDIO', 'Decoding audio data...');
      const audioBuffer = await ctx.decodeAudioData(bytes);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(analyserRef.current!);
      source.connect(ctx.destination);
      
      log('AUDIO', 'Sarah starting speech playback');
      setIsAiSpeaking(true);
      isAiSpeakingRef.current = true;
      source.start();
      
      source.onended = () => {
        log('AUDIO', 'Sarah speech playback ended');
        setIsAiSpeaking(false);
        isAiSpeakingRef.current = false;
        startRecording();
      };
    } catch (err) {
      log('AUDIO', `Playback error: ${err}`);
      setIsAiSpeaking(false);
      isAiSpeakingRef.current = false;
      startRecording();
    }
  }, [initAudio]);

  // --- WebSocket Logic ---
  const connectWebSocket = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host.replace(':3000', ':8000')}/ws/interview/${token}`;
    
    log('WS', `Connecting to: ${wsUrl}`);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        const data = jsonParse(event.data);
        log('WS', `Received ${data.type} message`);
        if (data.type === 'transcript') {
          setMessages(prev => [...prev, { role: data.role, text: data.text }]);
        } else if (data.type === 'turn_complete') {
          log('WS', 'Turn Complete: Re-opening microphone...');
          setIsProcessing(false);
          isProcessingRef.current = false;
          startRecording();
        } else if (data.type === 'error') {
          log('WS', `Server Error: ${data.message}`);
          setError(data.message);
        }
      } else {
        const buffer = await event.data.arrayBuffer();
        playAudioBytes(buffer);
      }
    };

    ws.onopen = () => log('WS', 'Connected to backend');
    ws.onclose = () => log('WS', 'Disconnected from backend');
    ws.onerror = (e) => log('WS', `Socket error: ${e}`);
  }, [token]);

  function jsonParse(str: string) {
    try { return JSON.parse(str); } catch { return {}; }
  }

  // --- Recording logic ---
  const startRecording = useCallback(async () => {
    log('MIC', 'Attempting to open microphone...');
    
    // Safety check
    if (isProcessingRef.current) {
      log('MIC', 'Opening blocked: Server is still processing/thinking');
      return;
    }
    if (isAiSpeakingRef.current) {
      log('MIC', 'Opening blocked: Sarah is still speaking');
      return;
    }
    if (state !== 'live') {
      log('MIC', `Opening blocked: State is ${state}`);
      return;
    }
    if (isRecording) {
      log('MIC', 'Opening blocked: Already recording');
      return;
    }

    try {
      initAudio();
      let stream = streamRef.current;
      if (!stream || !stream.active) {
        log('MIC', 'Requesting new media stream...');
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
      }
      
      log('MIC', 'Initializing MediaRecorder...');
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      recorder.start(250); 
      setIsRecording(true);
      log('MIC', 'Microphone is LIVE and streaming chunks');
      
      if (audioContextRef.current && analyserRef.current) {
        if (micSourceRef.current) micSourceRef.current.disconnect();
        const source = audioContextRef.current.createMediaStreamSource(stream);
        source.connect(analyserRef.current);
        micSourceRef.current = source;
      }
    } catch (err) {
      log('MIC', `Mic error: ${err}`);
      setError('Microphone access denied.');
    }
  }, [state, isRecording, initAudio]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      log('MIC', 'Stopping recording, sending turn_done');
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsProcessing(true);
      isProcessingRef.current = true;
      
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'turn_done' }));
      }
    }
  }, [isRecording]);

  const handleStart = async () => {
    log('UI', 'Start Interview clicked');
    if (isProcessing) return;
    setIsProcessing(true);
    isProcessingRef.current = true;
    try {
      initAudio();
      log('UI', 'Requesting microphone permission...');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      connectWebSocket();
      setState('live');
    } catch (err) {
      log('UI', `Setup failed: ${err}`);
      setError('Mic access required.');
      setIsProcessing(false);
      isProcessingRef.current = false;
    }
  };

  // --- Waveform Visualization ---
  useEffect(() => {
    if (!canvasRef.current || !analyserRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d')!;
    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    let animationId: number;
    const render = () => {
      animationId = requestAnimationFrame(render);
      analyser.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const barWidth = (canvas.width / bufferLength);
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const h = (dataArray[i] / 255) * canvas.height;
        const g = ctx.createLinearGradient(0, canvas.height - h, 0, canvas.height);
        g.addColorStop(0, '#a855f7'); g.addColorStop(1, '#3b82f6');
        ctx.fillStyle = g;
        ctx.fillRect(x, canvas.height - h, barWidth - 1, Math.max(4, h));
        x += barWidth;
      }
    };
    render();
    return () => cancelAnimationFrame(animationId);
  }, [state]);

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
  const cs: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)' };

  if (state === 'error') return (
    <div style={cs}>
      <div style={{ background: 'var(--bg-secondary)', padding: 40, borderRadius: 16, border: '1px solid var(--border-subtle)', textAlign: 'center' }}>
        <h2 style={{ color: '#ef4444' }}>Interview Error</h2>
        <p style={{ margin: '12px 0 24px' }}>{error}</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Try Again</button>
      </div>
    </div>
  );

  if (state === 'connecting') return <div style={cs}><div className="spinner" /></div>;

  if (state === 'welcome') return (
    <div style={cs}>
      <div style={{ width: 440, background: 'var(--bg-secondary)', borderRadius: 20, padding: 40, border: '1px solid var(--border-subtle)' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, textAlign: 'center', marginBottom: 32 }}>Welcome, {interview?.candidate_name}</h1>
        <button className="btn btn-primary btn-lg" onClick={handleStart} disabled={isProcessing} style={{ width: '100%' }}>
          {isProcessing ? 'Connecting...' : '🎤 Start Interview'}
        </button>
      </div>
    </div>
  );

  if (state === 'ending') return <div style={cs}><div className="spinner" /></div>;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      <header style={{ padding: '14px 28px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700 }}>{interview?.job_title}</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <span style={{ fontSize: 22, fontWeight: 700 }}>{fmt(timeLeft)}</span>
          <button onClick={() => setState('ending')} className="btn btn-sm btn-outline-danger">End</button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, width: '100%', maxWidth: 600 }}>
            <canvas ref={canvasRef} width={600} height={120} />
          </div>
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
              {isAiSpeaking ? 'Sarah is speaking...' : isProcessing ? 'Thinking...' : '🎤 Speak now'}
            </p>
            <button
              onClick={stopRecording}
              disabled={!isRecording || isProcessing}
              className="btn btn-lg"
              style={{
                borderRadius: 32, padding: '16px 48px',
                background: isRecording ? 'var(--accent-emerald)' : 'rgba(255,255,255,0.05)',
                color: isRecording ? '#fff' : 'var(--text-muted)'
              }}
            >
              {isProcessing ? 'Thinking...' : isAiSpeaking ? 'Sarah Speaking' : '✓ I\'m Done'}
            </button>
          </div>
        </div>

        <div style={{ width: 360, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: 16, borderBottom: '1px solid var(--border-subtle)', fontWeight: 600 }}>Transcript</div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ alignSelf: m.role === 'ai' ? 'flex-start' : 'flex-end', maxWidth: '85%' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{m.role === 'ai' ? 'Sarah' : 'You'}</span>
                <div style={{ background: m.role === 'ai' ? 'var(--bg-elevated)' : 'var(--accent-purple)', padding: '10px 14px', borderRadius: 12, fontSize: 13 }}>
                  {m.text}
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
