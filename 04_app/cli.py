"""Command-line interface for scoring individual or CSV job postings."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fraud_detector import FraudDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Score fraudulent job-posting risk.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    text_parser = subparsers.add_parser("text", help="Score one job posting.")
    text_parser.add_argument("--title", default="")
    text_parser.add_argument("--company-profile", default="")
    text_parser.add_argument("--description", required=True)
    text_parser.add_argument("--requirements", default="")
    text_parser.add_argument("--benefits", default="")

    csv_parser = subparsers.add_parser("csv", help="Score a CSV file.")
    csv_parser.add_argument("--input", required=True, type=Path)
    csv_parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    detector = FraudDetector()

    if args.command == "text":
        score, priority = detector.score_record(
            {
                "title": args.title,
                "company_profile": args.company_profile,
                "description": args.description,
                "requirements": args.requirements,
                "benefits": args.benefits,
            }
        )
        print(f"Risk ranking score: {score:.6f}")
        print(f"Review priority: {priority}")
    else:
        frame = pd.read_csv(args.input)
        result = detector.score_frame(frame)
        result.to_csv(args.output, index=False)
        print(f"Wrote {len(result):,} ranked rows to {args.output}")


if __name__ == "__main__":
    main()
