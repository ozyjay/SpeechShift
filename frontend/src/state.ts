import type { StreamEvent } from "./types";

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

export function pipelineErrorMessage(code?: string): string {
  if (code === "audio_silent") return "No clear speech was detected. Please record again and speak a little louder.";
  if (code === "audio_too_short") return "The recording was too short. Please hold the button longer.";
  return `Pipeline error: ${code ?? "unknown"}`;
}
