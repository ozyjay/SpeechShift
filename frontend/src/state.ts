import type { StreamEvent } from "./types";

export const stageOrder = ["spoken", "recognised", "translated", "generated"] as const;

export function acceptsEvent(event: StreamEvent, generation: number, lastSequence: number): boolean {
  if (event.generation !== undefined && event.generation !== generation) return false;
  if (event.sequence !== undefined && event.sequence <= lastSequence) return false;
  return true;
}

export function formatLatency(milliseconds: number, replayTiming: boolean): string {
  const seconds = (milliseconds / 1000).toFixed(1);
  return replayTiming ? `${seconds} s prepared timing` : `${seconds} s measured`;
}

