import { describe, expect, it } from "vitest";

import {
  BoundedSampleBuffer,
  encodeMonoWav,
  listAudioOutputs,
  resampleLinear,
  resolveAudioOutputDeviceId,
  setAudioOutput,
  SequencedPcmOutput,
  sequencedPcm16Frames,
  supportsAudioOutputSelection,
} from "./audio";

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

describe("audio output routing", () => {
  it("reports support only when the media target can select a sink", () => {
    expect(supportsAudioOutputSelection({ setSinkId: async () => undefined })).toBe(true);
    expect(supportsAudioOutputSelection({})).toBe(false);
  });

  it("lists only audio output devices", async () => {
    const devices = [
      { kind: "audioinput", deviceId: "microphone" },
      { kind: "audiooutput", deviceId: "headphones" },
    ] as MediaDeviceInfo[];
    await expect(listAudioOutputs(async () => devices)).resolves.toEqual([devices[1]]);
  });

  it("routes every player to the explicitly selected output", async () => {
    const selected: string[] = [];
    await setAudioOutput([
      { setSinkId: async (deviceId) => { selected.push(`original:${deviceId}`); } },
      { setSinkId: async (deviceId) => { selected.push(`result:${deviceId}`); } },
    ], "headphones");
    expect(selected).toEqual(["original:headphones", "result:headphones"]);
  });

  it("falls back to the system default when the selected output disappears", () => {
    const devices = [{ kind: "audiooutput", deviceId: "speakers" }] as MediaDeviceInfo[];
    expect(resolveAudioOutputDeviceId("speakers", devices)).toBe("speakers");
    expect(resolveAudioOutputDeviceId("headphones", devices)).toBe("");
    expect(resolveAudioOutputDeviceId("", devices)).toBe("");
  });

  it("fails rather than silently ignoring an unsupported player", async () => {
    await expect(setAudioOutput([{}], "headphones")).rejects.toThrow("does not support");
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

  it("frames PCM with sequence numbers and rebuilds streamed output", async () => {
    const frames = sequencedPcm16Frames(new Float32Array([0, 0.5, -0.5]), 2);
    expect(frames).toHaveLength(2);
    expect(new DataView(frames[0]).getUint32(0, true)).toBe(1);
    expect(new DataView(frames[1]).getUint32(0, true)).toBe(2);
    const output = new SequencedPcmOutput(32);
    frames.forEach((frame) => output.append(frame));
    const wav = output.consumeWav(16_000);
    expect(wav.size).toBe(50);
  });
});
