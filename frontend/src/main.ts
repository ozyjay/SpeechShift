import "./styles.css";

import { acceptsEvent, formatLatency } from "./state";
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
      <p class="eyebrow">A prepared AI speech demonstration</p>
      <h1>One sentence.<br><em>A whole new sound.</em></h1>
      <p class="hero-copy">Hear how a speech system can regenerate words with different vocal characteristics—or translate their meaning into another language.</p>
    </section>

    <section class="privacy-strip" aria-label="Privacy information">
      <span class="privacy-icon">◎</span>
      <div><strong>Replay mode uses prepared audio.</strong><br><span>The microphone is off. No visitor audio or personal details are collected.</span></div>
      <span class="replay-tag">PREPARED RUN</span>
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
        <div class="mic-state"><span class="mic-off">×</span><div><strong>Microphone off</strong><small>Replay uses an approved prepared sentence</small></div></div>
        <button id="startButton" class="start-button" type="button"><span class="play-icon">▶</span><span><b>Play the transformation</b><small>About 3 seconds</small></span></button>
      </div>
    </section>

    <section id="journey" class="journey" aria-live="polite">
      <div class="journey-heading"><div><p class="eyebrow">What is happening</p><h2>The speech journey</h2></div><div id="latency" class="latency">Ready for a prepared run</div></div>
      <div class="stage-track">
        <article class="stage" data-stage="spoken"><span class="stage-number">1</span><div class="wave mini-wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><h3>Spoken audio</h3><p>Prepared source clip</p></article>
        <span class="arrow">→</span>
        <article class="stage" data-stage="recognised"><span class="stage-number">2</span><div class="stage-icon">Aa</div><h3>Recognised words</h3><p id="transcript">Waiting…</p></article>
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
      <p class="accuracy-note">AI-produced voices and translations are approximations and may contain errors. Replay timings illustrate the intended experience; they are not live-model measurements.</p>
    </section>
  </main>

  <aside id="staffPanel" class="staff-panel" aria-hidden="true">
    <div class="staff-header"><div><p class="eyebrow">Staff only</p><h2>Operator controls</h2></div><button id="closeStaff" class="icon-button" type="button">×</button></div>
    <section><h3>Selected provider</h3><div id="providerList"></div><p class="operator-note">Provider changes are deliberately disabled in this replay-first build. A live provider must pass readiness and rehearsal gates first.</p></section>
    <section><h3>Session diagnostics</h3><dl class="diagnostics"><div><dt>Connection</dt><dd id="connectionState">Idle</dd></div><div><dt>Session</dt><dd id="sessionState">None</dd></div><div><dt>Storage</dt><dd>Memory only</dd></div><div><dt>Port status</dt><dd id="portState">Development proposal</dd></div></dl></section>
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

const audio = element<HTMLAudioElement>("#audioPlayer");
const startButton = element<HTMLButtonElement>("#startButton");
const cancelButton = element<HTMLButtonElement>("#cancelButton");
const replayButton = element<HTMLButtonElement>("#replayButton");

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
  lastAudioUrl = null;
  audio.pause();
  audio.removeAttribute("src");
  element("#transcript").textContent = "Waiting…";
  element("#translation").textContent = "Waiting…";
  element("#outputLabel").textContent = "Waiting…";
  element("#latency").textContent = "Ready for a prepared run";
  document.querySelectorAll(".stage").forEach((stage) => stage.classList.remove("active", "complete"));
  startButton.disabled = false;
  cancelButton.disabled = true;
  replayButton.disabled = true;
  stopWaveform();
}

function setStage(stageName: string): void {
  const stages = mode === "voice" ? ["spoken", "recognised", "generated"] : ["spoken", "recognised", "translated", "generated"];
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
  if (event.type === "transcript_final") element("#transcript").textContent = event.text ?? "";
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
  if (event.type === "metrics" && event.first_audio_latency_ms !== undefined) {
    element("#latency").textContent = formatLatency(event.first_audio_latency_ms, Boolean(event.replay_timing));
  }
  if (event.type === "complete") {
    document.querySelectorAll(".stage").forEach((stage) => stage.classList.add("complete"));
    startButton.disabled = false;
    cancelButton.disabled = true;
    element("#sessionState").textContent = "Complete";
  }
  if (event.type === "cancelled") {
    resetJourney();
    element("#sessionState").textContent = "Cancelled";
  }
}

async function createAndConnectSession(): Promise<void> {
  const response = await fetch("/api/sessions", { method: "POST" });
  if (!response.ok) throw new Error("Could not create a private session");
  const data = await response.json() as { session_id: string; generation: number };
  sessionId = data.session_id;
  generation = data.generation;
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/sessions/${sessionId}`);
  await new Promise<void>((resolve, reject) => {
    if (!socket) return reject(new Error("WebSocket unavailable"));
    socket.addEventListener("open", () => resolve(), { once: true });
    socket.addEventListener("error", () => reject(new Error("Replay connection failed")), { once: true });
  });
  socket.addEventListener("message", (message) => handleEvent(JSON.parse(message.data) as StreamEvent));
  socket.addEventListener("close", () => { element("#connectionState").textContent = "Disconnected"; });
  element("#connectionState").textContent = "Connected";
  element("#sessionState").textContent = `Active · ${sessionId.slice(0, 6)}`;
}

async function startRun(): Promise<void> {
  if (!socket || socket.readyState !== WebSocket.OPEN) await createAndConnectSession();
  resetJourney();
  startButton.disabled = true;
  cancelButton.disabled = false;
  element("#latency").textContent = "Prepared sequence running…";
  element("#journey").scrollIntoView({ behavior: "smooth", block: "start" });
  socket?.send(JSON.stringify({ command: "start", request: { mode, sentence_id: selectedSentence, selection_id: selectedOption } }));
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
    const row = document.createElement("div");
    row.className = `provider-row ${provider.id === config.provider ? "selected" : ""}`;
    row.innerHTML = `<span class="provider-radio"></span><div><b></b><small></small></div><span class="provider-state"></span>`;
    row.querySelector("b")!.textContent = provider.label;
    row.querySelector("small")!.textContent = provider.detail;
    row.querySelector<HTMLElement>(".provider-state")!.textContent = provider.state === "ready" ? "Ready" : "Unavailable";
    return row;
  }));
}

async function initialise(): Promise<void> {
  const [configResponse, catalogueResponse] = await Promise.all([fetch("/api/config"), fetch("/api/replay/catalogue")]);
  if (!configResponse.ok || !catalogueResponse.ok) throw new Error("SpeechShift could not load its local replay data");
  config = await configResponse.json() as PublicConfig;
  catalogue = await catalogueResponse.json() as Catalogue;
  element("#providerLabel").textContent = config.provider_label;
  element("#portState").textContent = config.port_allocation_confirmed ? "Confirmed" : "Development proposal";
  renderProviders();
  renderChoices();

  document.querySelectorAll<HTMLButtonElement>(".mode-tab").forEach((tab) => tab.addEventListener("click", () => setMode(tab.dataset.mode as ShiftMode)));
  startButton.addEventListener("click", () => void startRun().catch(showError));
  cancelButton.addEventListener("click", () => socket?.send(JSON.stringify({ command: "cancel" })));
  replayButton.addEventListener("click", () => { if (lastAudioUrl) { audio.src = lastAudioUrl; void audio.play(); startWaveform(); } });
  element("#resetButton").addEventListener("click", () => void clearSession());
  element("#staffReset").addEventListener("click", () => void clearSession());
  element("#muteButton").addEventListener("click", () => {
    muted = !muted; audio.volume = muted ? 0 : config.safe_output_volume;
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
  window.addEventListener("beforeunload", () => { socket?.close(); });
}

function showError(error: unknown): void {
  element("#latency").textContent = error instanceof Error ? error.message : "A local error occurred";
  startButton.disabled = false; cancelButton.disabled = true;
}

void initialise().catch(showError);

