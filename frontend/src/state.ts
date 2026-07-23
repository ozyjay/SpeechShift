import type { StreamEvent } from "./types";

export interface SourcePresentation {
  heading: string;
  title: string;
  detail: string;
  selectable: boolean;
}

export function sourcePresentation(provider: string, capturedSeconds?: number): SourcePresentation {
  if (provider === "local" || provider === "modeldeck") {
    return {
      heading: "Input recording",
      title: "Your recording",
      detail: capturedSeconds === undefined
        ? "Record a sample above to use as the input"
        : `${capturedSeconds.toFixed(1)} seconds captured in memory`,
      selectable: false,
    };
  }
  if (provider === "mock-modeldeck") {
    return {
      heading: "Choose a fixture sentence",
      title: "Fixture sentence",
      detail: "Mock text and output follow this prepared fixture",
      selectable: true,
    };
  }
  return {
    heading: "Choose a sentence",
    title: "Prepared sentence",
    detail: "This chooses the prepared source clip",
    selectable: true,
  };
}

export const stageOrder = ["spoken", "recognised", "translated", "generated"] as const;

export function acceptsEvent(event: StreamEvent, generation: number, lastSequence: number): boolean {
  if (event.generation !== undefined && event.generation !== generation) return false;
  if (event.sequence !== undefined && event.sequence <= lastSequence) return false;
  return true;
}

export function formatLatency(
  milliseconds: number,
  replayTiming: boolean,
  mockTiming = false,
  dspProcessing = false,
): string {
  const seconds = (milliseconds / 1000).toFixed(1);
  if (dspProcessing) return `${milliseconds} ms local DSP`;
  if (mockTiming) return `${seconds} s mock timing`;
  return replayTiming ? `${seconds} s prepared timing` : `${seconds} s measured`;
}

export function formatTaskElapsed(elapsedSeconds: number): string {
  const wholeSeconds = Math.max(0, Math.floor(elapsedSeconds));
  if (wholeSeconds < 60) return `${wholeSeconds} s elapsed`;
  const minutes = Math.floor(wholeSeconds / 60);
  const seconds = wholeSeconds % 60;
  return `${minutes} min ${seconds} s elapsed`;
}

export function pipelineErrorMessage(code?: string): string {
  if (code === "audio_silent") return "No clear speech was detected. Please record again and speak a little louder.";
  if (code === "audio_too_short") return "The recording was too short. Please hold the button longer.";
  if (code === "modeldeck_unavailable" || code === "local_route_unavailable") {
    return "The local AI pipeline is unavailable. Please ask a staff member to check ModelDeck.";
  }
  if (code === "thermal_cooldown_required") {
    return "The local AI hardware is cooling down. Please wait before trying again.";
  }
  if (code === "thermal_limit_reached") {
    return "The local AI pipeline stopped at its thermal safety limit. Please let the hardware cool down.";
  }
  if (code === "thermal_monitor_unavailable") {
    return "The local AI safety monitor is unavailable. Please ask a staff member to check ModelDeck.";
  }
  if (code === "modeldeck_timeout" || code === "deadline_exceeded" || code === "recognition_timeout") {
    return "The local AI pipeline took too long and was stopped safely. Please try again.";
  }
  return `Pipeline error: ${code ?? "unknown"}`;
}
