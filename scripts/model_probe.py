from __future__ import annotations

import argparse
import sys
from pathlib import Path

from speechshift.model_readiness import (
    CandidateManifest,
    candidate_licence_failures,
    load_probe_record,
    prepare_probe_record,
    readiness_failures,
)
from speechshift.tts_burn_in import run_tts_burn_in
from speechshift.tts_probe import SysfsHardwareMonitor, TtsProbeOutcome, run_isolated_tts_probe


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a candidate or prepare and evaluate a SpeechShift model-readiness record."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Capture the local fingerprint for a candidate.")
    prepare.add_argument("candidate", type=Path)
    prepare.add_argument("output", type=Path)
    evaluate = subparsers.add_parser("evaluate", help="Check whether a completed record passes every gate.")
    evaluate.add_argument("record", type=Path)
    audit = subparsers.add_parser(
        "audit",
        help="Fail unless the candidate code and every declared artefact have reviewed licences.",
    )
    audit.add_argument("candidate", type=Path)
    tts = subparsers.add_parser(
        "probe-tts",
        help="Run the pinned TTS candidate in an offline, cancellable worker process.",
    )
    tts.add_argument("candidate", type=Path)
    tts.add_argument("model", type=Path)
    tts.add_argument("output", type=Path)
    tts.add_argument("--python", type=Path, default=Path(sys.executable))
    tts.add_argument("--startup-timeout", type=float, default=60)
    tts.add_argument("--generation-timeout", type=float, default=90)
    tts.add_argument("--cancel-after", type=float)
    burn_in = subparsers.add_parser(
        "burn-in-tts",
        help="Repeat TTS completion, cancellation and timeout probes with thermal cut-offs.",
    )
    burn_in.add_argument("candidate", type=Path)
    burn_in.add_argument("model", type=Path)
    burn_in.add_argument("output", type=Path)
    burn_in.add_argument("--python", type=Path, default=Path(sys.executable))
    burn_in.add_argument("--cycles", type=int, default=10)
    burn_in.add_argument("--startup-timeout", type=float, default=60)
    burn_in.add_argument("--generation-timeout", type=float, default=90)
    burn_in.add_argument("--cancel-after", type=float, default=2)
    burn_in.add_argument("--forced-timeout", type=float, default=2)
    burn_in.add_argument("--memory-recovery-timeout", type=float, default=10)
    burn_in.add_argument("--cooldown-timeout", type=float, default=300)
    args = parser.parse_args()

    if args.command == "audit":
        candidate = CandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
        failures = candidate_licence_failures(candidate)
        if failures:
            print("Candidate downloads are blocked:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("Candidate code and declared artefact licences are reviewed.")
        return 0

    if args.command == "prepare":
        candidate = CandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
        record = prepare_probe_record(candidate)
        args.output.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"Prepared model probe record: {args.output}")
        return 0

    if args.command == "probe-tts":
        candidate = CandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
        failures = candidate_licence_failures(candidate)
        if candidate.capability != "speech.synthesise":
            failures.append("candidate does not provide speech synthesis")
        if failures:
            print("Candidate probe is blocked:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        worker = Path(__file__).with_name("qwen_tts_probe_worker.py")
        result = run_isolated_tts_probe(
            [str(args.python), str(worker), str(args.model)],
            startup_timeout_seconds=args.startup_timeout,
            generation_timeout_seconds=args.generation_timeout,
            cancel_after_seconds=args.cancel_after,
            hardware_monitor=SysfsHardwareMonitor.discover(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"TTS probe result: {result.outcome} ({args.output})")
        if result.outcome in {TtsProbeOutcome.COMPLETED, TtsProbeOutcome.CANCELLED}:
            return 0
        return 1

    if args.command == "burn-in-tts":
        candidate = CandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
        failures = candidate_licence_failures(candidate)
        if candidate.capability != "speech.synthesise":
            failures.append("candidate does not provide speech synthesis")
        if failures:
            print("Candidate burn-in is blocked:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        worker = Path(__file__).with_name("qwen_tts_probe_worker.py")
        summary = run_tts_burn_in(
            [str(args.python), str(worker), str(args.model)],
            SysfsHardwareMonitor.discover(),
            cycles=args.cycles,
            startup_timeout_seconds=args.startup_timeout,
            generation_timeout_seconds=args.generation_timeout,
            cancel_after_seconds=args.cancel_after,
            forced_timeout_seconds=args.forced_timeout,
            memory_recovery_timeout_seconds=args.memory_recovery_timeout,
            cooldown_timeout_seconds=args.cooldown_timeout,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
        status = "passed" if summary.passed else "failed"
        print(f"TTS burn-in {status}: {summary.cycles_completed}/{summary.cycles_requested} cycles")
        print(f"Burn-in result: {args.output}")
        return 0 if summary.passed else 1

    record = load_probe_record(args.record)
    failures = readiness_failures(record)
    if failures:
        print("Candidate is not ready:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Candidate passes the recorded SpeechShift readiness gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
