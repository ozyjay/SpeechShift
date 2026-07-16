import { describe, expect, it } from "vitest";

import { BoundedSampleBuffer, encodeMonoWav, resampleLinear } from "./audio";

describe("bounded audio buffering", () => {
  it("never accepts more than its configured maximum", () => {
    const buffer = new BoundedSampleBuffer(5);
    expect(buffer.append(new Float32Array([0.1, 0.2, 0.3]))).toBe(3);
    expect(buffer.append(new Float32Array([0.4, 0.5, 0.6]))).toBe(2);
    expect(buffer.append(new Float32Array([0.7]))).toBe(0);
    expect(buffer.full).toBe(true);
    expect(Array.from(buffer.consume())).toEqual([
      expect.closeTo(0.1),
      expect.closeTo(0.2),
      expect.closeTo(0.3),
      expect.closeTo(0.4),
      expect.closeTo(0.5),
    ]);
    expect(buffer.length).toBe(0);
  });
});

describe("audio conversion", () => {
  it("resamples to the target duration", () => {
    const source = new Float32Array(48_000);
    const output = resampleLinear(source, 48_000, 16_000);
    expect(output.length).toBe(16_000);
  });

  it("writes a mono 16-bit PCM WAV header", async () => {
    const wav = encodeMonoWav(new Float32Array([0, 1, -1]), 16_000);
    const bytes = new Uint8Array(await wav.arrayBuffer());
    expect(new TextDecoder().decode(bytes.slice(0, 4))).toBe("RIFF");
    expect(new TextDecoder().decode(bytes.slice(8, 12))).toBe("WAVE");
    expect(wav.size).toBe(50);
  });
});

