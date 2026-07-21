import { afterEach, describe, expect, it, vi } from "vitest";

import { InactivityReset } from "./inactivity";

describe("InactivityReset", () => {
  afterEach(() => vi.useRealTimers());

  it("warns, accepts activity and resets only after the renewed deadline", async () => {
    vi.useFakeTimers();
    const warnings: Array<number | null> = [];
    const onReset = vi.fn();
    const inactivity = new InactivityReset({
      timeoutSeconds: 120,
      warningSeconds: 15,
      onWarning: (remaining) => warnings.push(remaining),
      onReset,
    });

    inactivity.arm();
    await vi.advanceTimersByTimeAsync(105_000);
    expect(warnings.at(-1)).toBe(15);

    await vi.advanceTimersByTimeAsync(1_000);
    expect(warnings.at(-1)).toBe(14);
    inactivity.activity();
    expect(warnings.at(-1)).toBeNull();

    await vi.advanceTimersByTimeAsync(119_999);
    expect(onReset).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(onReset).toHaveBeenCalledOnce();
    expect(warnings.at(-1)).toBeNull();
  });

  it("does nothing until armed and cancels all work when disarmed", async () => {
    vi.useFakeTimers();
    const onWarning = vi.fn();
    const onReset = vi.fn();
    const inactivity = new InactivityReset({ timeoutSeconds: 30, onWarning, onReset });

    inactivity.activity();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(onReset).not.toHaveBeenCalled();

    inactivity.arm();
    inactivity.disarm();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(onReset).not.toHaveBeenCalled();
    expect(onWarning).toHaveBeenLastCalledWith(null);
  });
});
