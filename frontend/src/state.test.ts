import { describe, expect, it } from "vitest";

import { acceptsEvent, formatLatency } from "./state";

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
});
