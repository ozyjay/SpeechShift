export interface InactivityResetOptions {
  timeoutSeconds: number;
  warningSeconds?: number;
  onWarning: (remainingSeconds: number | null) => void;
  onReset: () => void | Promise<void>;
}

export class InactivityReset {
  readonly #timeoutMilliseconds: number;
  readonly #warningMilliseconds: number;
  readonly #onWarning: (remainingSeconds: number | null) => void;
  readonly #onReset: () => void | Promise<void>;
  #warningTimer: ReturnType<typeof setTimeout> | null = null;
  #resetTimer: ReturnType<typeof setTimeout> | null = null;
  #countdownTimer: ReturnType<typeof setInterval> | null = null;
  #warningDeadline = 0;
  #armed = false;

  constructor(options: InactivityResetOptions) {
    if (!Number.isFinite(options.timeoutSeconds) || options.timeoutSeconds <= 0) {
      throw new Error("Inactivity timeout must be positive");
    }
    const warningSeconds = Math.min(
      options.warningSeconds ?? 15,
      Math.max(1, options.timeoutSeconds / 2),
    );
    this.#timeoutMilliseconds = options.timeoutSeconds * 1_000;
    this.#warningMilliseconds = warningSeconds * 1_000;
    this.#onWarning = options.onWarning;
    this.#onReset = options.onReset;
  }

  arm(): void {
    this.#armed = true;
    this.#schedule();
  }

  activity(): void {
    if (this.#armed) this.#schedule();
  }

  disarm(): void {
    this.#armed = false;
    this.#clearTimers();
    this.#onWarning(null);
  }

  #schedule(): void {
    this.#clearTimers();
    this.#onWarning(null);
    this.#warningTimer = setTimeout(
      () => this.#startWarning(),
      this.#timeoutMilliseconds - this.#warningMilliseconds,
    );
    this.#resetTimer = setTimeout(() => {
      this.disarm();
      void this.#onReset();
    }, this.#timeoutMilliseconds);
  }

  #startWarning(): void {
    this.#warningDeadline = Date.now() + this.#warningMilliseconds;
    this.#updateWarning();
    this.#countdownTimer = setInterval(() => this.#updateWarning(), 1_000);
  }

  #updateWarning(): void {
    const remainingSeconds = Math.max(1, Math.ceil((this.#warningDeadline - Date.now()) / 1_000));
    this.#onWarning(remainingSeconds);
  }

  #clearTimers(): void {
    if (this.#warningTimer !== null) clearTimeout(this.#warningTimer);
    if (this.#resetTimer !== null) clearTimeout(this.#resetTimer);
    if (this.#countdownTimer !== null) clearInterval(this.#countdownTimer);
    this.#warningTimer = null;
    this.#resetTimer = null;
    this.#countdownTimer = null;
  }
}
