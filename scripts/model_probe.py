from __future__ import annotations

import argparse
from pathlib import Path

from speechshift.model_readiness import (
    CandidateManifest,
    load_probe_record,
    prepare_probe_record,
    readiness_failures,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare or evaluate a SpeechShift model-readiness record.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Capture the local fingerprint for a candidate.")
    prepare.add_argument("candidate", type=Path)
    prepare.add_argument("output", type=Path)
    evaluate = subparsers.add_parser("evaluate", help="Check whether a completed record passes every gate.")
    evaluate.add_argument("record", type=Path)
    args = parser.parse_args()

    if args.command == "prepare":
        candidate = CandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
        record = prepare_probe_record(candidate)
        args.output.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"Prepared model probe record: {args.output}")
        return 0

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
