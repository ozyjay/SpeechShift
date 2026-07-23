import { describe, expect, it } from "vitest";

import {
  acceptsEvent,
  formatLatency,
  formatTaskElapsed,
  pipelineErrorMessage,
  sourcePresentation,
} from "./state";

describe("stream state", () => {
  it("rejects stale generations and repeated sequences", () => {
    expect(acceptsEvent({ type: "state", generation: 2, sequence: 1 }, 2, 0)).toBe(true);
    expect(acceptsEvent({ type: "state", generation: 1, sequence: 2 }, 2, 0)).toBe(false);
    expect(acceptsEvent({ type: "state", generation: 2, sequence: 3 }, 2, 3)).toBe(false);
  });

  it("labels replay timing honestly", () => {
    expect(formatLatency(1540, true)).toBe("1.5 s prepared timing");
    expect(formatLatency(1540, false)).toBe("1.5 s measured");
    expect(formatLatency(1540, false, true)).toBe("1.5 s mock timing");
    expect(formatLatency(42, false, false, true)).toBe("42 ms local DSP");
  });

  it("formats elapsed task time without implying a completion percentage", () => {
    expect(formatTaskElapsed(-1)).toBe("0 s elapsed");
    expect(formatTaskElapsed(39.9)).toBe("39 s elapsed");
    expect(formatTaskElapsed(60)).toBe("1 min 0 s elapsed");
    expect(formatTaskElapsed(125)).toBe("2 min 5 s elapsed");
  });

  it("turns input gate failures into visitor-safe guidance", () => {
    expect(pipelineErrorMessage("audio_silent")).toContain("No clear speech was detected");
    expect(pipelineErrorMessage("audio_too_short")).toContain("too short");
    expect(pipelineErrorMessage("modeldeck_unavailable")).toContain("local AI pipeline is unavailable");
    expect(pipelineErrorMessage("modeldeck_timeout")).toContain("stopped safely");
    expect(pipelineErrorMessage("recognition_timeout")).toContain("stopped safely");
    expect(pipelineErrorMessage("thermal_cooldown_required")).toContain("cooling down");
    expect(pipelineErrorMessage("thermal_limit_reached")).toContain("thermal safety limit");
    expect(pipelineErrorMessage("thermal_monitor_unavailable")).toContain("safety monitor");
    expect(pipelineErrorMessage("unexpected")).toBe("Pipeline error: unexpected");
  });

  it("presents captured audio as the Local DSP input without a sentence choice", () => {
    expect(sourcePresentation("local", 1.25)).toEqual({
      heading: "Input recording",
      title: "Your recording",
      detail: "1.3 seconds captured in memory",
      selectable: false,
    });
    expect(sourcePresentation("replay").selectable).toBe(true);
    expect(sourcePresentation("mock-modeldeck").heading).toBe("Choose a fixture sentence");
    expect(sourcePresentation("modeldeck").selectable).toBe(false);
  });
});
