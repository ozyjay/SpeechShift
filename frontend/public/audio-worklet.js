class SpeechShiftCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel?.length) {
      const frame = new Float32Array(channel);
      this.port.postMessage(frame, [frame.buffer]);
    }
    return true;
  }
}

registerProcessor("speechshift-capture", SpeechShiftCaptureProcessor);

