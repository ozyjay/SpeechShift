import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright-core";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, "..");
const pythonPath = join(repoRoot, ".venv", "bin", "python");
const port = Number.parseInt(process.env.SPEECHSHIFT_BROWSER_TEST_PORT ?? "3810", 10);
const baseUrl = `http://127.0.0.1:${port}`;
let server;
let browser;
let serverOutput = "";

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function appendServerOutput(chunk) {
  serverOutput = `${serverOutput}${String(chunk)}`.slice(-8_000);
}

async function findExecutable() {
  const candidates = [
    process.env.SPEECHSHIFT_CHROMIUM,
    "chromium-browser",
    "chromium",
    "google-chrome-stable",
    "google-chrome",
  ].filter(Boolean);
  const pathDirectories = (process.env.PATH ?? "").split(":").filter(Boolean);
  for (const candidate of candidates) {
    const paths = isAbsolute(candidate)
      ? [candidate]
      : pathDirectories.map((directory) => join(directory, candidate));
    for (const path of paths) {
      try {
        await access(path, constants.X_OK);
        return path;
      } catch {
        // Try the next known system browser path.
      }
    }
  }
  throw new Error(
    "System Chromium was not found. Install chromium-browser or set SPEECHSHIFT_CHROMIUM.",
  );
}

async function waitForServer() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (server.exitCode !== null) {
      throw new Error(`SpeechShift test server exited early.\n${serverOutput}`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok && (await response.json()).status === "ready") return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error(`SpeechShift test server did not become ready.\n${serverOutput}`);
}

async function stopServer() {
  if (!server || server.exitCode !== null) return;
  server.kill("SIGINT");
  await Promise.race([
    new Promise((resolveExit) => server.once("exit", resolveExit)),
    new Promise((resolveWait) => setTimeout(resolveWait, 2_000)),
  ]);
  if (server.exitCode === null) server.kill("SIGTERM");
}

async function selectProvider(page, name, expectedLabel = name) {
  const row = page.locator("#providerList").getByRole("button", { name: new RegExp(name, "i") });
  await row.click();
  await page.locator("#providerLabel").getByText(expectedLabel, { exact: true }).waitFor();
}

async function verifyMuteControl(page) {
  const button = page.locator("#muteButton");
  check(await button.getAttribute("aria-label") === "Mute output", "Mute control has the wrong initial label");
  check(await button.locator("svg").count() === 1, "Mute control is missing its speaker icon");
  await button.click();
  check(await button.getAttribute("aria-pressed") === "true", "Mute control did not enter its pressed state");
  check(await button.getAttribute("aria-label") === "Unmute output", "Muted control has the wrong label");
  await button.click();
  check(await button.getAttribute("aria-pressed") === "false", "Mute control did not restore its state");
}

async function verifyReplayCombinations(page, catalogue) {
  const successfulAudio = new Set();
  const failedAudio = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith("/replay/") || !url.pathname.endsWith(".wav")) return;
    if (response.ok()) successfulAudio.add(url.pathname);
    else failedAudio.push(`${response.status()} ${url.pathname}`);
  });

  for (const mode of ["voice", "language"]) {
    await page.locator(`.mode-tab[data-mode="${mode}"]`).click();
    const collection = mode === "voice" ? "voices" : "languages";
    for (let sentenceIndex = 0; sentenceIndex < catalogue.sentences.length; sentenceIndex += 1) {
      const sentence = catalogue.sentences[sentenceIndex];
      await page.locator("#sentenceChoices button").nth(sentenceIndex).click();
      check(
        await page.locator("#sentenceChoices .selected b").textContent() === sentence.prompt,
        `${mode}: sentence card did not select ${sentence.prompt}`,
      );
      for (let optionIndex = 0; optionIndex < sentence[collection].length; optionIndex += 1) {
        const option = sentence[collection][optionIndex];
        await page.locator("#selectionChoices button").nth(optionIndex).click();
        check(
          await page.locator("#selectionChoices .selected b").textContent() === option.label,
          `${sentence.prompt}: option card did not select ${option.label}`,
        );
        await page.locator("#startButton").click();
        await page.waitForFunction(() => (
          document.querySelector("#sessionState")?.textContent === "Complete"
          && !document.querySelector("#replayButton")?.disabled
        ), undefined, { timeout: 8_000 });
        await page.waitForFunction(() => {
          const player = document.querySelector("#audioPlayer");
          return player instanceof HTMLAudioElement && player.readyState >= 1 && player.error === null;
        }, undefined, { timeout: 4_000 });
        check(
          await page.locator("#outputLabel").textContent() === option.label,
          `${sentence.prompt}: completed output did not match ${option.label}`,
        );
        const audioPath = await page.locator("#audioPlayer").evaluate((player) => (
          new URL(player.currentSrc).pathname
        ));
        check(audioPath === `/replay/${option.audio}`, `${option.label}: unexpected audio ${audioPath}`);
        await page.locator("#resetButton").click();
        await page.waitForFunction(() => (
          document.querySelector("#sessionState")?.textContent === "Cleared"
          && document.querySelector("#replayButton")?.disabled
          && document.querySelector("#transcript")?.textContent === "Waiting…"
        ));
      }
    }
  }

  check(failedAudio.length === 0, `Replay audio requests failed: ${failedAudio.join(", ")}`);
  const expectedResultAudio = catalogue.sentences.flatMap((sentence) => [
    ...sentence.voices.map((option) => option.audio),
    ...sentence.languages.map((option) => option.audio),
  ]).map((path) => `/replay/${path}`);
  const missingResultAudio = expectedResultAudio.filter((path) => !successfulAudio.has(path));
  check(
    missingResultAudio.length === 0,
    `Replay result audio was not loaded: ${missingResultAudio.join(", ")}`,
  );

  const catalogueAudio = catalogue.sentences.flatMap((sentence) => [
    sentence.original_audio,
    ...sentence.voices.map((option) => option.audio),
    ...sentence.languages.map((option) => option.audio),
  ]);
  for (const path of catalogueAudio) {
    const response = await page.request.get(`${baseUrl}/replay/${path}`);
    check(response.ok(), `Replay catalogue audio is unavailable: ${path}`);
  }
}

async function verifyProviderPresentation(page) {
  await page.locator("#staffButton").click();
  await selectProvider(page, "Local DSP");
  check(await page.locator("#sourceHeading").textContent() === "Input recording", "Local DSP input heading is misleading");
  check(await page.locator("#sentenceChoices button").count() === 0, "Local DSP still exposes sentence buttons");
  check(await page.locator("#recordedSourceDetail").textContent() === "Record a sample above to use as the input", "Local DSP input guidance is missing");
  check(await page.locator("#sentenceChoices .recorded-source b").textContent() === "Your recording", "Local DSP does not identify the recording as input");
  check(await page.locator('.mode-tab[data-mode="language"]').isDisabled(), "Local DSP still enables Language Shift");
  check(await page.locator("#startButton").isDisabled(), "Local DSP can start without a recording");
  check(await page.locator("#selectionChoices button").count() === 4, "Local DSP profiles are incomplete");
  await page.locator("#closeStaff").click();
  const anonymised = page.locator("#selectionChoices").getByRole("button", { name: /Anonymised voice/i });
  await anonymised.click();
  check(await anonymised.locator("small").textContent() === "Experimental formant reshaping that keeps the recording's timing", "Anonymised voice limitations are unclear");

  await page.locator("#staffButton").click();
  await selectProvider(page, "Mock contract");
  check(await page.locator("#sourceHeading").textContent() === "Choose a fixture sentence", "Mock sentence choices are not labelled as fixtures");
  check(await page.locator("#sentenceChoices button").count() === 3, "Mock fixture choices are incomplete");
  check(!await page.locator('.mode-tab[data-mode="language"]').isDisabled(), "Mock Language Shift is unexpectedly disabled");

  await selectProvider(page, "Replay", "Replay mode");
  check(await page.locator("#sourceHeading").textContent() === "Choose a sentence", "Replay sentence heading was not restored");
  check(await page.locator("#sentenceChoices button").count() === 3, "Replay sentence choices were not restored");
  check(await page.locator("#selectionChoices .selected").count() === 1, "Replay retained an invalid local-only profile");
}

async function verifyReadableTypography(page) {
  const selectors = [
    ".microphone-copy > p:last-child",
    "#recordHint",
    ".choice-card small",
    ".option-card small",
    ".stage p",
    ".generation-progress small",
    ".accuracy-note",
    ".operator-note",
  ];
  for (const selector of selectors) {
    const size = await page.locator(selector).first().evaluate(
      (node) => Number.parseFloat(window.getComputedStyle(node).fontSize),
    );
    check(size >= 12.4, `${selector} is still too small at ${size}px`);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(mobileOverflow <= 1, `Larger typography causes ${mobileOverflow}px of mobile horizontal overflow`);
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function verifyInactivityReset(page) {
  await page.route("**/api/config", async (route) => {
    const response = await route.fetch();
    const config = await response.json();
    config.visitor_idle_timeout_seconds = 2;
    await route.fulfill({ response, json: config });
  });
  await page.reload({ waitUntil: "networkidle" });
  await page.locator("#providerLabel").getByText("Replay mode", { exact: true }).waitFor();

  await page.locator("#startButton").click();
  const warning = page.locator("#inactivityWarning");
  await warning.waitFor({ state: "visible", timeout: 2_000 });
  await page.locator(".journey-heading").click();
  await warning.waitFor({ state: "hidden" });
  await warning.waitFor({ state: "visible", timeout: 2_000 });
  await page.waitForFunction(() => (
    document.querySelector("#sessionState")?.textContent === "Cleared · inactivity timeout"
  ), undefined, { timeout: 2_000 });

  check(await warning.isHidden(), "Inactivity warning remained visible after reset");
  check(await page.locator("#transcript").textContent() === "Waiting…", "Inactivity reset retained transcript text");
  check(await page.locator("#audioPlayer").getAttribute("src") === null, "Inactivity reset retained result audio");
  check(await page.locator("#providerLabel").textContent() === "Replay mode", "Inactivity reset changed provider");
}

async function main() {
  await access(pythonPath, constants.X_OK);
  const chromiumPath = await findExecutable();
  server = spawn(pythonPath, ["-m", "speechshift"], {
    cwd: repoRoot,
    env: {
      ...process.env,
      APP_HOST: "127.0.0.1",
      APP_PORT: String(port),
      DEMO_MODE: "development",
      SPEECH_PROVIDER: "replay",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.stdout.on("data", appendServerOutput);
  server.stderr.on("data", appendServerOutput);
  await waitForServer();

  browser = await chromium.launch({ executablePath: chromiumPath, headless: true });
  const page = await browser.newPage({ locale: "en-AU", viewport: { width: 1440, height: 1000 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#providerLabel").getByText("Replay mode", { exact: true }).waitFor();
  const catalogue = await (await fetch(`${baseUrl}/api/replay/catalogue`)).json();

  await verifyReadableTypography(page);
  await verifyMuteControl(page);
  await verifyReplayCombinations(page, catalogue);
  await verifyProviderPresentation(page);
  await verifyInactivityReset(page);
  console.log("Browser smoke passed: replay combinations, provider semantics, audio loading, reset and inactivity clearing.");
}

try {
  await main();
} finally {
  await browser?.close();
  await stopServer();
}
