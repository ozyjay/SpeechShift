import "./styles.css";

import {
  type CapturedAudio,
  listAudioOutputs,
  listMicrophones,
  microphoneErrorMessage,
  MicrophoneRecorder,
  requestMicrophonePermission,
  resolveAudioOutputDeviceId,
  setAudioOutput,
  SequencedPcmOutput,
  sequencedPcm16Frames,
  supportsAudioOutputSelection,
} from "./audio";
import { acceptsEvent, formatLatency, pipelineErrorMessage } from "./state";
import type { Catalogue, PublicConfig, Sentence, ShiftMode, StreamEvent } from "./types";

const root = document.querySelector<HTMLDivElement>("#app");
if (!root) throw new Error("Application root is missing");

root.innerHTML = `
  <div class="ambient ambient-one"></div><div class="ambient ambient-two"></div>
  <header class="topbar">
    <a class="brand" href="#" aria-label="SpeechShift home">
      <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
      <span>Speech<span>Shift</span></span>
    </a>
    <div class="top-actions">
      <div class="provider-pill"><span class="status-dot"></span><strong id="providerLabel">Loading…</strong></div>
      <button class="icon-button" id="muteButton" type="button" aria-pressed="false" title="Mute output">◖</button>
      <button class="staff-button" id="staffButton" type="button">Operator controls <span>⌘</span></button>
    </div>
  </header>

  <main>
    <section class="hero">
      <p class="eyebrow">A local-first AI speech demonstration</p>
      <h1>One sentence.<br><em>A whole new sound.</em></h1>
      <p class="hero-copy">Hear how a speech system can regenerate words with different vocal characteristics—or translate their meaning into another language.</p>
    </section>

    <section class="privacy-strip" aria-label="Privacy information">
      <span class="privacy-icon">◎</span>
      <div><strong id="privacyHeading">The transformation remains a prepared replay.</strong><br><span id="privacyDetail">The optional microphone check stays in browser memory and is cleared on reset.</span></div>
      <span class="replay-tag">PREPARED RUN</span>
    </section>

    <section class="microphone-card" aria-labelledby="microphoneHeading">
      <div class="microphone-copy">
        <p class="eyebrow">Local audio check</p>
        <h2 id="microphoneHeading">Try your microphone</h2>
        <p id="microphoneExplanation">Hold to record up to <span id="maxSeconds">8</span> seconds, then hear your original voice. It is not uploaded or used by the prepared transformation.</p>
      </div>
      <div class="microphone-controls">
        <div class="device-row">
          <select id="microphoneSelect" aria-label="Microphone device" disabled><option>Permission required</option></select>
          <button id="enableMicrophone" class="secondary-button" type="button">Enable microphone</button>
        </div>
        <div class="capture-row">
          <button id="recordButton" class="record-button" type="button" disabled><span class="record-dot"></span><span><b>Hold to record</b><small id="recordHint">Microphone is off</small></span></button>
          <div class="level-shell" aria-label="Live microphone level"><span id="inputLevel"></span></div>
          <button id="playOriginal" class="secondary-button" type="button" disabled>▶ Play original</button>
          <button id="clearOriginal" class="text-button" type="button" disabled>Clear</button>
        </div>
        <audio id="localAudioPlayer" preload="metadata"></audio>
        <p id="microphoneStatus" class="microphone-status" role="status">Microphone inactive. Replay is ready without permission.</p>
      </div>
      <span class="memory-badge">MEMORY ONLY</span>
    </section>

    <section class="experience-card">
      <div class="mode-tabs" role="tablist" aria-label="Choose an experience">
        <button class="mode-tab active" data-mode="voice" role="tab" aria-selected="true"><span>◒</span><b>Voice Shift</b><small>Same words, a new vocal style</small></button>
        <button class="mode-tab" data-mode="language" role="tab" aria-selected="false"><span>文</span><b>Language Shift</b><small>Same meaning, another language</small></button>
      </div>

      <div class="builder">
        <div class="choice-column">
          <label class="step-label"><span>1</span> Choose a sentence</label>
          <div id="sentenceChoices" class="choice-stack"></div>
        </div>
        <div class="choice-column">
          <label class="step-label"><span>2</span> <span id="selectionHeading">Choose a voice</span></label>
          <div id="selectionChoices" class="choice-grid"></div>
        </div>
      </div>

      <div class="action-row">
        <div class="mic-state"><span class="mic-off">R</span><div><strong>Prepared transformation</strong><small>Your microphone recording is not sent to replay</small></div></div>
        <button id="startButton" class="start-button" type="button"><span class="play-icon">▶</span><span><b>Play the transformation</b><small>About 3 seconds</small></span></button>
      </div>
    </section>

    <section id="journey" class="journey" aria-live="polite">
      <div class="journey-heading"><div><p class="eyebrow">What is happening</p><h2>The speech journey</h2></div><div id="latency" class="latency">Ready for a prepared run</div></div>
      <div class="stage-track">
        <article class="stage" data-stage="spoken"><span class="stage-number">1</span><div class="wave mini-wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><h3>Spoken audio</h3><p>Prepared source clip</p></article>
        <span class="arrow recognition-stage">→</span>
        <article class="stage recognition-stage" data-stage="recognised"><span class="stage-number">2</span><div class="stage-icon">Aa</div><h3>Recognised words</h3><p id="transcript">Waiting…</p></article>
        <span class="arrow language-stage">→</span>
        <article class="stage language-stage" data-stage="translated"><span class="stage-number">3</span><div class="stage-icon">文</div><h3>Translated meaning</h3><p id="translation">Waiting…</p></article>
        <span class="arrow">→</span>
        <article class="stage" data-stage="generated"><span class="stage-number" id="generatedNumber">3</span><div class="wave mini-wave reverse"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><h3>Generated speech</h3><p id="outputLabel">Waiting…</p></article>
      </div>
      <div class="result-player">
        <canvas id="waveform" width="900" height="110" aria-label="Animated audio waveform"></canvas>
        <audio id="audioPlayer" preload="auto"></audio>
        <div class="player-controls"><button id="replayButton" disabled type="button">↻ Replay result</button><button id="cancelButton" disabled type="button">■ Cancel</button><button id="resetButton" type="button">Next visitor / Reset</button></div>
      </div>
      <p id="accuracyNote" class="accuracy-note">AI-produced voices and translations are approximations and may contain errors. Replay timings illustrate the intended experience; they are not live-model measurements.</p>
    </section>
  </main>

  <aside id="staffPanel" class="staff-panel" aria-hidden="true">
    <div class="staff-header"><div><p class="eyebrow">Staff only</p><h2>Operator controls</h2></div><button id="closeStaff" class="icon-button" type="button">×</button></div>
    <section><h3>Selected provider</h3><div id="providerList"></div><p id="providerNote" class="operator-note">Replay is ready. The deterministic mock contract is available only for supervised development testing.</p></section>
    <section><h3>Playback output</h3><label class="operator-field" for="outputSelect">Output device</label><select id="outputSelect" class="operator-select" disabled><option>Checking browser support…</option></select><p id="outputStatus" class="operator-note" role="status">Checking available outputs…</p></section>
    <section><h3>Session diagnostics</h3><dl class="diagnostics"><div><dt>Connection</dt><dd id="connectionState">Idle</dd></div><div><dt>Session</dt><dd id="sessionState">None</dd></div><div><dt>Microphone</dt><dd id="microphoneDiagnostic">Inactive</dd></div><div><dt>Output</dt><dd id="outputDiagnostic">Checking</dd></div><div><dt>Storage</dt><dd>Memory only</dd></div><div><dt>Port status</dt><dd id="portState">Development proposal</dd></div></dl></section>
    <button id="staffReset" class="danger-button" type="button">Cancel and clear session</button>
  </aside>
  <div id="scrim" class="scrim"></div>
`;

const element = <T extends HTMLElement>(selector: string): T => {
  const found = document.querySelector<T>(selector);
  if (!found) throw new Error(`Missing element: ${selector}`);
  return found;
};

let config: PublicConfig;
let catalogue: Catalogue;
let mode: ShiftMode = "voice";
let selectedSentence = "campus";
let selectedOption = "calm-narrator";
let sessionId: string | null = null;
let generation = 0;
let lastSequence = 0;
let socket: WebSocket | null = null;
let lastAudioUrl: string | null = null;
let muted = false;
let animationFrame = 0;
let microphoneRecorder: MicrophoneRecorder;
let microphonePermission = false;
let localAudioUrl: string | null = null;
let finishingCapture = false;
let recordIntent = false;
let capturedAudio: CapturedAudio | null = null;
let streamedOutput: SequencedPcmOutput | null = null;
let streamedOutputSampleRate = 16_000;
let selectedOutputDeviceId = "";

const audio = element<HTMLAudioElement>("#audioPlayer");
const localAudio = element<HTMLAudioElement>("#localAudioPlayer");
const startButton = element<HTMLButtonElement>("#startButton");
const cancelButton = element<HTMLButtonElement>("#cancelButton");
const replayButton = element<HTMLButtonElement>("#replayButton");
const recordButton = element<HTMLButtonElement>("#recordButton");

function updateMicrophoneState(message: string, state: "inactive" | "ready" | "recording" | "captured" | "error"): void {
  element("#microphoneStatus").textContent = message;
  element("#microphoneDiagnostic").textContent = {
    inactive: "Inactive",
    ready: "Ready · inactive",
    recording: "Recording",
    captured: "Captured in memory",
    error: "Needs attention",
  }[state];
  recordButton.classList.toggle("recording", state === "recording");
  element("#recordHint").textContent = state === "recording" ? "Release to stop" : "Microphone is off";
}

function updateStartAvailability(): void {
  const isMock = config?.provider === "mock-modeldeck";
  const isLocal = config?.provider === "local";
  startButton.disabled = (isMock || isLocal) && !capturedAudio;
  const title = startButton.querySelector("b");
  const detail = startButton.querySelector("small");
  if (title) title.textContent = isLocal
    ? "Apply local voice shift"
    : (isMock ? "Run mock pipeline" : "Play the transformation");
  if (detail) {
    detail.textContent = isLocal
      ? (capturedAudio ? "Real offline signal processing" : "Record a local sample first")
      : (isMock
          ? (capturedAudio ? "Streams your captured PCM to a deterministic mock" : "Record a local sample first")
          : "About 3 seconds");
  }
}

function updateProviderPresentation(): void {
  const isMock = config.provider === "mock-modeldeck";
  const isLocal = config.provider === "local";
  document.body.classList.toggle("local-dsp-mode", isLocal);
  const languageTab = document.querySelector<HTMLButtonElement>('.mode-tab[data-mode="language"]');
  if (languageTab) languageTab.disabled = isLocal;
  if (isLocal && mode !== "voice") setMode("voice");
  element("#providerLabel").textContent = config.provider_label;
  element("#privacyHeading").textContent = isLocal
    ? "Local DSP voice shift is selected."
    : (isMock ? "Development mock contract is selected." : "The transformation remains a prepared replay.");
  element("#privacyDetail").textContent = isLocal
    ? "Captured PCM is processed in memory by SpeechShift and cleared on reset. This is signal processing, not AI."
    : (isMock
        ? "Captured PCM crosses only to the local SpeechShift backend; text and output audio are deterministic fixtures."
        : "The optional microphone check stays in browser memory and is cleared on reset.");
  element("#microphoneExplanation").innerHTML = isLocal
    ? `Hold to record up to <span id="maxSeconds">${config.max_input_seconds}</span> seconds. Local DSP applies the selected voice effect without recognising or storing your words.`
    : (isMock
        ? `Hold to record up to <span id="maxSeconds">${config.max_input_seconds}</span> seconds. The local backend validates this PCM stream, but mock text and output are fixtures.`
        : `Hold to record up to <span id="maxSeconds">${config.max_input_seconds}</span> seconds, then hear your original voice. It is not uploaded or used by the prepared transformation.`);
  element("#accuracyNote").textContent = isLocal
    ? "Local DSP changes the sound directly and does not recognise words, translate speech or use an AI model. Results vary with microphone quality and speaking volume."
    : (isMock
        ? "Mock contract mode validates transport and interface behaviour only. Transcript, translation, timing and output audio are deterministic fixtures—not AI results."
        : "AI-produced voices and translations are approximations and may contain errors. Replay timings illustrate the intended experience; they are not live-model measurements.");
  element("#providerNote").textContent = isLocal
    ? "Local DSP is selected for real Voice Shift input. It is a development baseline, not a speech model, and Language Shift is unavailable."
    : (isMock
        ? "Mock contract is selected. It sends bounded audio to the local backend and uses deterministic fixtures. Switch back to Replay for the public story."
        : "Replay is selected. Local DSP and the deterministic mock contract are available for supervised development testing.");
  element("#generatedNumber").textContent = isLocal ? "2" : (mode === "voice" ? "3" : "4");
  updateStartAvailability();
}

async function refreshMicrophones(): Promise<void> {
  if (!microphonePermission) return;
  const select = element<HTMLSelectElement>("#microphoneSelect");
  const previous = select.value;
  const devices = await listMicrophones();
  select.replaceChildren(...devices.map((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Microphone ${index + 1}`;
    return option;
  }));
  select.disabled = devices.length === 0;
  if (devices.some((device) => device.deviceId === previous)) select.value = previous;
  recordButton.disabled = devices.length === 0;
  if (devices.length === 0) updateMicrophoneState("No microphone is currently available.", "error");
}

async function enableMicrophone(): Promise<void> {
  const button = element<HTMLButtonElement>("#enableMicrophone");
  button.disabled = true;
  updateMicrophoneState("Waiting for microphone permission…", "inactive");
  try {
    await requestMicrophonePermission();
    microphonePermission = true;
    await refreshMicrophones();
    await refreshAudioOutputs();
    button.textContent = "Permission granted";
    updateMicrophoneState("Ready. The microphone remains off until you hold the record button.", "ready");
  } catch (error) {
    button.disabled = false;
    updateMicrophoneState(microphoneErrorMessage(error), "error");
  }
}

function describeOutputDevice(deviceId: string, devices: MediaDeviceInfo[]): string {
  if (!deviceId) return "System default";
  return devices.find((device) => device.deviceId === deviceId)?.label || "Selected output";
}

async function refreshAudioOutputs(): Promise<void> {
  const select = element<HTMLSelectElement>("#outputSelect");
  const status = element("#outputStatus");
  const diagnostic = element("#outputDiagnostic");
  if (!supportsAudioOutputSelection(audio) || !navigator.mediaDevices?.enumerateDevices) {
    select.replaceChildren(new Option("Browser output selection unavailable", ""));
    select.disabled = true;
    status.textContent = "This browser uses the system default output. Select the booth device in system settings.";
    diagnostic.textContent = "System default · browser unsupported";
    return;
  }
  try {
    const devices = await listAudioOutputs();
    const selectableDevices = devices.filter((device) => device.deviceId !== "default");
    const options = [new Option("System default", ""), ...selectableDevices.map((device, index) => (
      new Option(device.label || `Audio output ${index + 1}`, device.deviceId)
    ))];
    select.replaceChildren(...options);
    select.disabled = false;
    if (selectedOutputDeviceId && !resolveAudioOutputDeviceId(selectedOutputDeviceId, selectableDevices)) {
      selectedOutputDeviceId = "";
      select.value = "";
      try {
        await setAudioOutput([audio, localAudio], "");
        status.textContent = "The selected output disconnected. Using the system default; choose another output if needed.";
        diagnostic.textContent = "Attention · system default";
      } catch {
        status.textContent = "The selected output disconnected and playback routing could not be restored. Check system audio settings.";
        diagnostic.textContent = "Needs attention";
      }
      return;
    }
    select.value = selectedOutputDeviceId;
    const label = describeOutputDevice(selectedOutputDeviceId, selectableDevices);
    status.textContent = selectedOutputDeviceId
      ? `Original and transformed playback are routed to ${label}.`
      : "Original and transformed playback use the system default output.";
    diagnostic.textContent = label;
  } catch {
    select.replaceChildren(new Option("Output devices unavailable", ""));
    select.disabled = true;
    status.textContent = "Output devices could not be listed. Check browser and system audio settings.";
    diagnostic.textContent = "Needs attention";
  }
}

async function selectAudioOutput(deviceId: string): Promise<void> {
  const select = element<HTMLSelectElement>("#outputSelect");
  const status = element("#outputStatus");
  const diagnostic = element("#outputDiagnostic");
  const previousDeviceId = selectedOutputDeviceId;
  select.disabled = true;
  status.textContent = "Changing playback output…";
  try {
    await setAudioOutput([audio, localAudio], deviceId);
    selectedOutputDeviceId = deviceId;
    const label = select.selectedOptions[0]?.textContent || "Selected output";
    status.textContent = deviceId
      ? `Original and transformed playback are routed to ${label}.`
      : "Original and transformed playback use the system default output.";
    diagnostic.textContent = label;
  } catch {
    select.value = previousDeviceId;
    await setAudioOutput([audio, localAudio], previousDeviceId).catch(() => undefined);
    status.textContent = "That output could not be selected. The previous playback route is still selected.";
    diagnostic.textContent = "Needs attention";
  } finally {
    select.disabled = false;
  }
}

function revokeLocalAudio(): void {
  localAudio.pause();
  localAudio.removeAttribute("src");
  if (localAudioUrl) URL.revokeObjectURL(localAudioUrl);
  localAudioUrl = null;
  capturedAudio = null;
  element<HTMLButtonElement>("#playOriginal").disabled = true;
  element<HTMLButtonElement>("#clearOriginal").disabled = true;
  updateStartAvailability();
}

async function beginMicrophoneCapture(): Promise<void> {
  if (!microphonePermission || microphoneRecorder.recording || finishingCapture) return;
  revokeLocalAudio();
  audio.pause();
  const selectedDevice = element<HTMLSelectElement>("#microphoneSelect").value;
  updateMicrophoneState("Starting microphone…", "inactive");
  try {
    await microphoneRecorder.start(selectedDevice);
    if (!recordIntent) {
      await finishMicrophoneCapture();
      return;
    }
    updateMicrophoneState("Recording locally. Release the button to stop.", "recording");
  } catch (error) {
    updateMicrophoneState(microphoneErrorMessage(error), "error");
  }
}

async function finishMicrophoneCapture(limitMessage?: string): Promise<void> {
  if (!microphoneRecorder.recording || finishingCapture) return;
  finishingCapture = true;
  updateMicrophoneState("Finishing local recording…", "inactive");
  try {
    const captured = await microphoneRecorder.stop();
    if (!captured || captured.durationSeconds < 0.15) {
      updateMicrophoneState("That recording was too short. Hold the button a little longer.", "ready");
      return;
    }
    localAudioUrl = URL.createObjectURL(captured.wav);
    capturedAudio = captured;
    localAudio.src = localAudioUrl;
    localAudio.volume = muted ? 0 : config.safe_output_volume;
    element<HTMLButtonElement>("#playOriginal").disabled = false;
    element<HTMLButtonElement>("#clearOriginal").disabled = false;
    const duration = captured.durationSeconds.toFixed(1);
    updateMicrophoneState(limitMessage ?? `Captured ${duration} seconds in browser memory.`, "captured");
    updateStartAvailability();
  } catch (error) {
    updateMicrophoneState(microphoneErrorMessage(error), "error");
  } finally {
    finishingCapture = false;
  }
}

async function clearMicrophoneCapture(message = "Local recording cleared. Microphone inactive."): Promise<void> {
  if (microphoneRecorder?.recording) await microphoneRecorder.cancel();
  finishingCapture = false;
  revokeLocalAudio();
  element<HTMLElement>("#inputLevel").style.width = "0%";
  updateMicrophoneState(message, microphonePermission ? "ready" : "inactive");
}

function currentSentence(): Sentence {
  const sentence = catalogue.sentences.find((item) => item.id === selectedSentence);
  if (!sentence) throw new Error("Selected sentence is unavailable");
  return sentence;
}

function renderChoices(): void {
  const sentenceChoices = element("#sentenceChoices");
  sentenceChoices.replaceChildren(
    ...catalogue.sentences.map((sentence) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `choice-card ${sentence.id === selectedSentence ? "selected" : ""}`;
      button.innerHTML = `<span class="radio"></span><span><b></b><small></small></span>`;
      button.querySelector("b")!.textContent = sentence.prompt;
      button.querySelector("small")!.textContent = sentence.source_text;
      button.addEventListener("click", () => {
        selectedSentence = sentence.id;
        const options = mode === "voice" ? sentence.voices : sentence.languages;
        if (!options.some((option) => option.id === selectedOption)) selectedOption = options[0].id;
        renderChoices();
      });
      return button;
    }),
  );

  const options = mode === "voice" ? currentSentence().voices : currentSentence().languages;
  const selectionChoices = element("#selectionChoices");
  selectionChoices.replaceChildren(
    ...options.map((option, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `option-card ${option.id === selectedOption ? "selected" : ""}`;
      const description = "description" in option ? option.description : option.text;
      button.innerHTML = `<span class="option-glyph">${["◌", "✦", "⌁"][index % 3]}</span><b></b><small></small>`;
      button.querySelector("b")!.textContent = option.label;
      button.querySelector("small")!.textContent = description;
      button.addEventListener("click", () => { selectedOption = option.id; renderChoices(); });
      return button;
    }),
  );
}

function setMode(nextMode: ShiftMode): void {
  mode = nextMode;
  selectedOption = mode === "voice" ? currentSentence().voices[0].id : currentSentence().languages[0].id;
  document.querySelectorAll<HTMLButtonElement>(".mode-tab").forEach((tab) => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.body.classList.toggle("language-mode", mode === "language");
  element("#selectionHeading").textContent = mode === "voice" ? "Choose a voice" : "Choose a language";
  element("#generatedNumber").textContent = mode === "voice" ? "3" : "4";
  resetJourney();
  renderChoices();
}

function resetJourney(): void {
  lastSequence = 0;
  if (lastAudioUrl?.startsWith("blob:")) URL.revokeObjectURL(lastAudioUrl);
  lastAudioUrl = null;
  streamedOutput?.clear();
  streamedOutput = null;
  audio.pause();
  audio.removeAttribute("src");
  element("#transcript").textContent = "Waiting…";
  element("#translation").textContent = "Waiting…";
  element("#outputLabel").textContent = "Waiting…";
  element("#latency").textContent = "Ready for a prepared run";
  document.querySelectorAll(".stage").forEach((stage) => stage.classList.remove("active", "complete"));
  updateStartAvailability();
  cancelButton.disabled = true;
  replayButton.disabled = true;
  stopWaveform();
}

function setStage(stageName: string): void {
  const stages = config.provider === "local"
    ? ["spoken", "generated"]
    : (mode === "voice" ? ["spoken", "recognised", "generated"] : ["spoken", "recognised", "translated", "generated"]);
  const activeIndex = stages.indexOf(stageName);
  stages.forEach((stage, index) => {
    const card = document.querySelector<HTMLElement>(`.stage[data-stage="${stage}"]`);
    card?.classList.toggle("active", index === activeIndex);
    card?.classList.toggle("complete", index < activeIndex);
  });
}

function handleEvent(event: StreamEvent): void {
  if (!acceptsEvent(event, generation, lastSequence)) return;
  if (event.sequence !== undefined) lastSequence = event.sequence;
  if (event.stage) setStage(event.stage);
  if (event.type === "transcript_partial" || event.type === "transcript_final") {
    element("#transcript").textContent = event.text ?? "";
  }
  if (event.type === "translation_final") element("#translation").textContent = event.text ?? "";
  if (event.type === "state" && event.stage === "generated") element("#outputLabel").textContent = event.detail ?? "Generating…";
  if (event.type === "audio" && event.audio_url) {
    if (event.stage === "generated") {
      lastAudioUrl = event.audio_url;
      element("#outputLabel").textContent = event.label ?? "Generated audio";
      audio.src = event.audio_url;
      audio.volume = muted ? 0 : config.safe_output_volume;
      replayButton.disabled = false;
      if (event.autoplay) void audio.play().catch(() => undefined);
    }
    startWaveform();
  }
  if (event.type === "audio_start") {
    streamedOutput?.clear();
    streamedOutput = new SequencedPcmOutput(2_000_000);
    streamedOutputSampleRate = event.audio_format?.sample_rate_hz ?? config.audio_sample_rate;
    element("#outputLabel").textContent = event.label ?? "Receiving mock audio…";
  }
  if (event.type === "audio_end" && streamedOutput) {
    if (lastAudioUrl?.startsWith("blob:")) URL.revokeObjectURL(lastAudioUrl);
    lastAudioUrl = URL.createObjectURL(streamedOutput.consumeWav(streamedOutputSampleRate));
    streamedOutput = null;
    audio.src = lastAudioUrl;
    audio.volume = muted ? 0 : config.safe_output_volume;
    replayButton.disabled = false;
    void audio.play().catch(() => undefined);
    startWaveform();
  }
  if (event.type === "metrics" && event.first_audio_latency_ms !== undefined) {
    element("#latency").textContent = formatLatency(
      event.first_audio_latency_ms,
      Boolean(event.replay_timing),
      Boolean(event.mock_timing),
      Boolean(event.dsp_processing),
    );
  }
  if (event.type === "complete") {
    document.querySelectorAll(".stage").forEach((stage) => stage.classList.add("complete"));
    updateStartAvailability();
    cancelButton.disabled = true;
    element("#sessionState").textContent = "Complete";
  }
  if (event.type === "cancelled") {
    resetJourney();
    element("#sessionState").textContent = "Cancelled";
  }
  if (event.type === "error") {
    element("#latency").textContent = pipelineErrorMessage(event.code);
    cancelButton.disabled = true;
    updateStartAvailability();
  }
}

function handleBinaryOutput(frame: ArrayBuffer): void {
  try {
    if (!streamedOutput) throw new Error("Unexpected output audio frame");
    streamedOutput.append(frame);
  } catch (error) {
    streamedOutput?.clear();
    streamedOutput = null;
    showError(error);
  }
}

async function createAndConnectSession(): Promise<void> {
  const response = await fetch("/api/sessions", { method: "POST" });
  if (!response.ok) throw new Error("Could not create a private session");
  const data = await response.json() as { session_id: string; generation: number };
  sessionId = data.session_id;
  generation = data.generation;
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/sessions/${sessionId}`);
  socket.binaryType = "arraybuffer";
  await new Promise<void>((resolve, reject) => {
    if (!socket) return reject(new Error("WebSocket unavailable"));
    socket.addEventListener("open", () => resolve(), { once: true });
    socket.addEventListener("error", () => reject(new Error("Replay connection failed")), { once: true });
  });
  socket.addEventListener("message", (message) => {
    if (message.data instanceof ArrayBuffer) handleBinaryOutput(message.data);
    else handleEvent(JSON.parse(String(message.data)) as StreamEvent);
  });
  socket.addEventListener("close", () => { element("#connectionState").textContent = "Disconnected"; });
  element("#connectionState").textContent = "Connected";
  element("#sessionState").textContent = `Active · ${sessionId.slice(0, 6)}`;
}

async function startRun(): Promise<void> {
  if (!socket || socket.readyState !== WebSocket.OPEN) await createAndConnectSession();
  resetJourney();
  startButton.disabled = true;
  cancelButton.disabled = false;
  element("#journey").scrollIntoView({ behavior: "smooth", block: "start" });
  if (config.provider === "mock-modeldeck" || config.provider === "local") {
    if (!capturedAudio) throw new Error("Record a local sample before running the mock contract.");
    element("#latency").textContent = config.provider === "local"
      ? "Applying local DSP in memory…"
      : "Sending bounded PCM to deterministic mock…";
    socket?.send(JSON.stringify({
      command: config.provider === "local" ? "start_local" : "start_mock",
      request: {
        mode,
        sentence_id: selectedSentence,
        selection_id: selectedOption,
        audio_format: { encoding: "pcm_s16le", sample_rate_hz: capturedAudio.sampleRate, channels: 1 },
      },
    }));
    await sendBinaryFrames(sequencedPcm16Frames(capturedAudio.samples));
    socket?.send(JSON.stringify({ command: "end_audio" }));
  } else {
    element("#latency").textContent = "Prepared sequence running…";
    socket?.send(JSON.stringify({
      command: "start",
      request: { mode, sentence_id: selectedSentence, selection_id: selectedOption },
    }));
  }
}

async function sendBinaryFrames(frames: ArrayBuffer[]): Promise<void> {
  if (!socket || socket.readyState !== WebSocket.OPEN) throw new Error("Pipeline connection is unavailable");
  const deadline = performance.now() + 3_000;
  for (const frame of frames) {
    while (socket.bufferedAmount > 64 * 1024) {
      if (performance.now() > deadline) throw new Error("Audio upload backpressure timeout");
      await new Promise((resolve) => window.setTimeout(resolve, 10));
    }
    socket.send(frame);
  }
}

async function clearSession(): Promise<void> {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ command: "cancel" }));
  socket?.close();
  socket = null;
  if (sessionId) await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" }).catch(() => undefined);
  sessionId = null;
  generation += 1;
  element("#connectionState").textContent = "Idle";
  element("#sessionState").textContent = "Cleared";
  await clearMicrophoneCapture();
  resetJourney();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function startWaveform(): void {
  const canvas = element<HTMLCanvasElement>("#waveform");
  const context = canvas.getContext("2d");
  if (!context || animationFrame) return;
  let tick = 0;
  const draw = (): void => {
    tick += 0.07;
    context.clearRect(0, 0, canvas.width, canvas.height);
    const gradient = context.createLinearGradient(0, 0, canvas.width, 0);
    gradient.addColorStop(0, "#42e7d8"); gradient.addColorStop(0.55, "#8f72ff"); gradient.addColorStop(1, "#ff9e5e");
    context.strokeStyle = gradient; context.lineWidth = 3; context.beginPath();
    for (let x = 0; x <= canvas.width; x += 4) {
      const envelope = Math.sin(Math.PI * x / canvas.width);
      const y = canvas.height / 2 + Math.sin(x * 0.055 + tick) * 27 * envelope * (0.65 + 0.35 * Math.sin(x * 0.013 - tick));
      x === 0 ? context.moveTo(x, y) : context.lineTo(x, y);
    }
    context.stroke();
    animationFrame = requestAnimationFrame(draw);
  };
  draw();
}

function stopWaveform(): void {
  cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  const canvas = element<HTMLCanvasElement>("#waveform");
  canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
}

function renderProviders(): void {
  element("#providerList").replaceChildren(...config.providers.map((provider) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `provider-row ${provider.id === config.provider ? "selected" : ""}`;
    row.innerHTML = `<span class="provider-radio"></span><div><b></b><small></small></div><span class="provider-state"></span>`;
    row.querySelector("b")!.textContent = provider.label;
    row.querySelector("small")!.textContent = provider.detail;
    row.querySelector<HTMLElement>(".provider-state")!.textContent = provider.state === "ready" ? "Ready" : "Unavailable";
    row.disabled = provider.state !== "ready" || provider.id === config.provider;
    if (provider.state === "ready") {
      row.addEventListener("click", () => void selectProvider(provider.id).catch(showError));
    }
    return row;
  }));
}

async function selectProvider(provider: string): Promise<void> {
  await clearSession();
  const response = await fetch("/api/providers/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider }),
  });
  if (!response.ok) {
    const error = await response.json() as { detail?: string };
    throw new Error(error.detail ?? "Provider selection failed");
  }
  config = await response.json() as PublicConfig;
  renderProviders();
  updateProviderPresentation();
}

async function initialise(): Promise<void> {
  const [configResponse, catalogueResponse] = await Promise.all([fetch("/api/config"), fetch("/api/replay/catalogue")]);
  if (!configResponse.ok || !catalogueResponse.ok) throw new Error("SpeechShift could not load its local replay data");
  config = await configResponse.json() as PublicConfig;
  catalogue = await catalogueResponse.json() as Catalogue;
  microphoneRecorder = new MicrophoneRecorder(config.audio_sample_rate, config.max_input_seconds, {
    onLevel: (level) => { element<HTMLElement>("#inputLevel").style.width = `${Math.round(level * 100)}%`; },
    onLimitReached: () => {
      recordIntent = false;
      void finishMicrophoneCapture(`Maximum ${config.max_input_seconds} seconds captured in browser memory.`);
    },
    onDeviceEnded: () => {
      recordIntent = false;
      void clearMicrophoneCapture("Microphone disconnected. The local recording was cleared.");
    },
  });
  element("#portState").textContent = config.port_allocation_confirmed ? "Confirmed" : "Development proposal";
  renderProviders();
  updateProviderPresentation();
  renderChoices();
  await refreshAudioOutputs();

  document.querySelectorAll<HTMLButtonElement>(".mode-tab").forEach((tab) => tab.addEventListener("click", () => setMode(tab.dataset.mode as ShiftMode)));
  startButton.addEventListener("click", () => void startRun().catch(showError));
  cancelButton.addEventListener("click", () => {
    socket?.send(JSON.stringify({ command: "cancel" }));
    recordIntent = false;
    if (microphoneRecorder.recording) void clearMicrophoneCapture("Recording cancelled and cleared.");
  });
  replayButton.addEventListener("click", () => { if (lastAudioUrl) { audio.src = lastAudioUrl; void audio.play(); startWaveform(); } });
  element("#enableMicrophone").addEventListener("click", () => void enableMicrophone());
  element("#playOriginal").addEventListener("click", () => {
    localAudio.currentTime = 0;
    localAudio.volume = muted ? 0 : config.safe_output_volume;
    void localAudio.play();
  });
  element("#clearOriginal").addEventListener("click", () => void clearMicrophoneCapture());
  element<HTMLSelectElement>("#outputSelect").addEventListener("change", (event) => {
    void selectAudioOutput((event.currentTarget as HTMLSelectElement).value);
  });
  recordButton.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    recordIntent = true;
    recordButton.setPointerCapture(event.pointerId);
    void beginMicrophoneCapture();
  });
  recordButton.addEventListener("pointerup", () => {
    recordIntent = false;
    void finishMicrophoneCapture();
  });
  recordButton.addEventListener("pointercancel", () => {
    recordIntent = false;
    void clearMicrophoneCapture("Recording cancelled and cleared.");
  });
  recordButton.addEventListener("keydown", (event) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      recordIntent = true;
      void beginMicrophoneCapture();
    }
  });
  recordButton.addEventListener("keyup", (event) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      recordIntent = false;
      void finishMicrophoneCapture();
    }
  });
  element("#resetButton").addEventListener("click", () => void clearSession());
  element("#staffReset").addEventListener("click", () => void clearSession());
  element("#muteButton").addEventListener("click", () => {
    muted = !muted;
    audio.volume = muted ? 0 : config.safe_output_volume;
    localAudio.volume = muted ? 0 : config.safe_output_volume;
    const button = element<HTMLButtonElement>("#muteButton");
    button.setAttribute("aria-pressed", String(muted)); button.textContent = muted ? "×" : "◖";
  });
  const toggleStaff = (open: boolean): void => {
    element("#staffPanel").classList.toggle("open", open); element("#scrim").classList.toggle("open", open);
    element("#staffPanel").setAttribute("aria-hidden", String(!open));
  };
  element("#staffButton").addEventListener("click", () => toggleStaff(true));
  element("#closeStaff").addEventListener("click", () => toggleStaff(false));
  element("#scrim").addEventListener("click", () => toggleStaff(false));
  navigator.mediaDevices?.addEventListener("devicechange", () => {
    void refreshMicrophones();
    void refreshAudioOutputs();
  });
  window.addEventListener("beforeunload", () => {
    socket?.close();
    void microphoneRecorder.cancel();
    revokeLocalAudio();
  });
}

function showError(error: unknown): void {
  element("#latency").textContent = error instanceof Error ? error.message : "A local error occurred";
  updateStartAvailability();
  cancelButton.disabled = true;
}

void initialise().catch(showError);
