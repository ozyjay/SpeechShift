export interface CapturedAudio {
  samples: Float32Array;
  sampleRate: number;
  durationSeconds: number;
  wav: Blob;
}

export interface RecorderCallbacks {
  onLevel: (level: number) => void;
  onLimitReached: () => void;
  onDeviceEnded: () => void;
}

export class BoundedSampleBuffer {
  readonly maximumSamples: number;
  #chunks: Float32Array[] = [];
  #length = 0;

  constructor(maximumSamples: number) {
    if (!Number.isInteger(maximumSamples) || maximumSamples < 1) {
      throw new Error("maximumSamples must be a positive integer");
    }
    this.maximumSamples = maximumSamples;
  }

  get length(): number {
    return this.#length;
  }

  get full(): boolean {
    return this.#length >= this.maximumSamples;
  }

  append(frame: Float32Array): number {
    const available = this.maximumSamples - this.#length;
    if (available <= 0 || frame.length === 0) return 0;
    const accepted = frame.length <= available ? frame.slice() : frame.slice(0, available);
    this.#chunks.push(accepted);
    this.#length += accepted.length;
    return accepted.length;
  }

  consume(): Float32Array {
    const output = new Float32Array(this.#length);
    let offset = 0;
    for (const chunk of this.#chunks) {
      output.set(chunk, offset);
      offset += chunk.length;
    }
    this.clear();
    return output;
  }

  clear(): void {
    this.#chunks = [];
    this.#length = 0;
  }
}

export function resampleLinear(input: Float32Array, sourceRate: number, targetRate: number): Float32Array {
  if (sourceRate <= 0 || targetRate <= 0) throw new Error("sample rates must be positive");
  if (input.length === 0 || sourceRate === targetRate) return input.slice();
  const outputLength = Math.max(1, Math.round(input.length * targetRate / sourceRate));
  const output = new Float32Array(outputLength);
  const scale = sourceRate / targetRate;
  for (let index = 0; index < outputLength; index += 1) {
    const position = index * scale;
    const before = Math.min(Math.floor(position), input.length - 1);
    const after = Math.min(before + 1, input.length - 1);
    const fraction = position - before;
    output[index] = input[before] * (1 - fraction) + input[after] * fraction;
  }
  return output;
}

export function encodeMonoWav(samples: Float32Array, sampleRate: number): Blob {
  const pcm = new Uint8Array(samples.length * 2);
  const pcmView = new DataView(pcm.buffer);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    pcmView.setInt16(index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return encodePcm16Wav(pcm, sampleRate);
}

export function encodePcm16Wav(pcm: Uint8Array, sampleRate: number): Blob {
  if (pcm.byteLength % 2 !== 0) throw new Error("PCM16 audio must contain complete samples");
  const dataLength = pcm.byteLength;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);
  const writeText = (offset: number, value: string): void => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, dataLength, true);
  new Uint8Array(buffer, 44).set(pcm);
  return new Blob([buffer], { type: "audio/wav" });
}

export function sequencedPcm16Frames(samples: Float32Array, frameSamples = 320): ArrayBuffer[] {
  if (!Number.isInteger(frameSamples) || frameSamples < 1) throw new Error("frameSamples must be positive");
  const frames: ArrayBuffer[] = [];
  let sequence = 1;
  for (let offset = 0; offset < samples.length; offset += frameSamples) {
    const length = Math.min(frameSamples, samples.length - offset);
    const frame = new ArrayBuffer(4 + length * 2);
    const view = new DataView(frame);
    view.setUint32(0, sequence, true);
    for (let index = 0; index < length; index += 1) {
      const sample = Math.max(-1, Math.min(1, samples[offset + index]));
      view.setInt16(4 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    }
    frames.push(frame);
    sequence += 1;
  }
  return frames;
}

export class SequencedPcmOutput {
  #maximumBytes: number;
  #chunks: Uint8Array[] = [];
  #length = 0;
  #nextSequence = 1;

  constructor(maximumBytes: number) {
    this.#maximumBytes = maximumBytes;
  }

  append(frame: ArrayBuffer): void {
    if (frame.byteLength <= 4) throw new Error("Invalid output audio frame");
    const view = new DataView(frame);
    if (view.getUint32(0, true) !== this.#nextSequence) throw new Error("Output audio sequence error");
    const audio = new Uint8Array(frame.slice(4));
    if (this.#length + audio.byteLength > this.#maximumBytes) throw new Error("Output audio buffer limit reached");
    this.#chunks.push(audio);
    this.#length += audio.byteLength;
    this.#nextSequence += 1;
  }

  consumeWav(sampleRate: number): Blob {
    const pcm = new Uint8Array(this.#length);
    let offset = 0;
    for (const chunk of this.#chunks) {
      pcm.set(chunk, offset);
      offset += chunk.byteLength;
    }
    this.clear();
    return encodePcm16Wav(pcm, sampleRate);
  }

  clear(): void {
    this.#chunks = [];
    this.#length = 0;
    this.#nextSequence = 1;
  }
}

export async function requestMicrophonePermission(): Promise<void> {
  ensureMicrophoneSupport();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  stream.getTracks().forEach((track) => track.stop());
}

export async function listMicrophones(): Promise<MediaDeviceInfo[]> {
  ensureMicrophoneSupport();
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === "audioinput");
}

export function microphoneErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return "Microphone permission was not granted. Replay remains available.";
    }
    if (error.name === "NotFoundError" || error.name === "OverconstrainedError") {
      return "The selected microphone is unavailable. Choose another device or use replay.";
    }
    if (error.name === "NotReadableError" || error.name === "AbortError") {
      return "The microphone is busy or could not start. Check other audio applications.";
    }
  }
  return error instanceof Error ? error.message : "The microphone could not start.";
}

export class MicrophoneRecorder {
  #targetSampleRate: number;
  #maxSeconds: number;
  #callbacks: RecorderCallbacks;
  #context: AudioContext | null = null;
  #stream: MediaStream | null = null;
  #source: MediaStreamAudioSourceNode | null = null;
  #worklet: AudioWorkletNode | null = null;
  #silentGain: GainNode | null = null;
  #analyser: AnalyserNode | null = null;
  #buffer: BoundedSampleBuffer | null = null;
  #animationFrame = 0;
  #limitTimer = 0;
  #recording = false;
  #stopping = false;

  constructor(targetSampleRate: number, maxSeconds: number, callbacks: RecorderCallbacks) {
    this.#targetSampleRate = targetSampleRate;
    this.#maxSeconds = maxSeconds;
    this.#callbacks = callbacks;
  }

  get recording(): boolean {
    return this.#recording;
  }

  async start(deviceId: string): Promise<void> {
    if (this.#recording) return;
    ensureMicrophoneSupport();
    if (!("AudioWorkletNode" in window)) throw new Error("This browser does not support low-latency audio capture.");
    this.#stopping = false;
    const audio: MediaTrackConstraints = {
      channelCount: { ideal: 1 },
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: false,
    };
    if (deviceId) audio.deviceId = { exact: deviceId };
    this.#stream = await navigator.mediaDevices.getUserMedia({ audio, video: false });
    this.#stream.getAudioTracks().forEach((track) => {
      track.addEventListener("ended", () => {
        if (!this.#stopping && this.#recording) this.#callbacks.onDeviceEnded();
      }, { once: true });
    });
    this.#context = new AudioContext({ latencyHint: "interactive" });
    await this.#context.audioWorklet.addModule("/audio-worklet.js");
    this.#buffer = new BoundedSampleBuffer(Math.ceil(this.#context.sampleRate * this.#maxSeconds));
    this.#source = this.#context.createMediaStreamSource(this.#stream);
    this.#analyser = this.#context.createAnalyser();
    this.#analyser.fftSize = 512;
    this.#analyser.smoothingTimeConstant = 0.65;
    this.#worklet = new AudioWorkletNode(this.#context, "speechshift-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    this.#silentGain = this.#context.createGain();
    this.#silentGain.gain.value = 0;
    this.#worklet.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (!this.#buffer || !this.#recording) return;
      this.#buffer.append(event.data);
      if (this.#buffer.full) this.#callbacks.onLimitReached();
    };
    this.#source.connect(this.#analyser);
    this.#source.connect(this.#worklet);
    this.#worklet.connect(this.#silentGain).connect(this.#context.destination);
    this.#recording = true;
    this.#monitorLevel();
    this.#limitTimer = window.setTimeout(() => this.#callbacks.onLimitReached(), this.#maxSeconds * 1000);
  }

  async stop(): Promise<CapturedAudio | null> {
    if (!this.#recording || !this.#context || !this.#buffer) return null;
    this.#recording = false;
    const sourceRate = this.#context.sampleRate;
    const sourceSamples = this.#buffer.consume();
    await this.#releaseResources();
    if (sourceSamples.length === 0) return null;
    const samples = resampleLinear(sourceSamples, sourceRate, this.#targetSampleRate);
    return {
      samples,
      sampleRate: this.#targetSampleRate,
      durationSeconds: samples.length / this.#targetSampleRate,
      wav: encodeMonoWav(samples, this.#targetSampleRate),
    };
  }

  async cancel(): Promise<void> {
    this.#recording = false;
    this.#buffer?.clear();
    await this.#releaseResources();
  }

  async #releaseResources(): Promise<void> {
    this.#stopping = true;
    window.clearTimeout(this.#limitTimer);
    cancelAnimationFrame(this.#animationFrame);
    this.#animationFrame = 0;
    this.#callbacks.onLevel(0);
    this.#worklet?.disconnect();
    this.#source?.disconnect();
    this.#analyser?.disconnect();
    this.#silentGain?.disconnect();
    this.#stream?.getTracks().forEach((track) => track.stop());
    if (this.#context && this.#context.state !== "closed") await this.#context.close();
    this.#context = null;
    this.#stream = null;
    this.#source = null;
    this.#worklet = null;
    this.#silentGain = null;
    this.#analyser = null;
    this.#buffer = null;
    this.#stopping = false;
  }

  #monitorLevel(): void {
    if (!this.#analyser || !this.#recording) return;
    const values = new Float32Array(this.#analyser.fftSize);
    this.#analyser.getFloatTimeDomainData(values);
    const sum = values.reduce((total, value) => total + value * value, 0);
    this.#callbacks.onLevel(Math.min(1, Math.sqrt(sum / values.length) * 4));
    this.#animationFrame = requestAnimationFrame(() => this.#monitorLevel());
  }
}

function ensureMicrophoneSupport(): void {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone capture requires a supported browser on localhost or a secure connection.");
  }
}
