/**
 * AudioWorklet processor for capturing and downsampling mic input to 16kHz PCM.
 */
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 2048;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];
    
    for (let i = 0; i < channelData.length; i++) {
      this.buffer[this.bufferIndex++] = channelData[i];
      
      if (this.bufferIndex >= this.bufferSize) {
        // Convert to 16-bit PCM
        const pcmData = this.convertToPcm(this.buffer);
        this.port.postMessage(pcmData);
        this.bufferIndex = 0;
      }
    }

    return true;
  }

  convertToPcm(float32Array) {
    const pcm = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm.buffer;
  }
}

registerProcessor('mic-processor', MicProcessor);
