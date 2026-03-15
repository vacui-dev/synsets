#!/usr/bin/env python3
"""
Validate — check ILI annotations against WordNet and golden examples.

Usage:
    python validate.py output.jsonl
    python validate.py output.jsonl --golden references/golden_examples.json
    python validate.py output.jsonl --strict  # fail on any invalid ILI
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import wn
except ImportError:
    print("ERROR: 'wn' package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)

from ili_lookup import ensure_wordnet, get_ili_id


def validate_ili_exists(ili_id: int) -> bool:
    """Check if an ILI ID corresponds to a real WordNet synset."""
    ili_str = f"i{ili_id}"
    try:
        synsets = wn.synsets(ili=ili_str)
        return len(synsets) > 0
    except Exception:
        return False


def validate_pos_match(ili_id: int, claimed_pos: str) -> bool:
    """Check if the claimed POS matches the actual WordNet POS for this ILI."""
    ili_str = f"i{ili_id}"
    try:
        synsets = wn.synsets(ili=ili_str)
        if not synsets:
            return False
        actual_pos = synsets[0].pos
        # Allow 's' (satellite adj) to match 'a' (adjective)
        if claimed_pos == "s":
            claimed_pos = "a"
        if actual_pos == "s":
            actual_pos = "a"
        return actual_pos == claimed_pos
    except Exception:
        return False


def validate_file(input_path: str, golden_path: str | None = None, strict: bool = False):
    """Validate a JSONL file of ILI annotations."""
    ensure_wordnet()

    lines = Path(input_path).read_text().strip().split("\n")
    records = [json.loads(line) for line in lines if line.strip()]

    total_annotations = 0
    valid_ili = 0
    invalid_ili = 0
    pos_match = 0
    pos_mismatch = 0
    invalid_ids = []

    print(f"Validating {len(records)} records from {input_path}...")

    for i, record in enumerate(records):
        annotations = record.get("annotations", [])
        for ann in annotations:
            total_annotations += 1
            ili = ann.get("ili")
            pos = ann.get("pos")

            if ili is None:
                invalid_ili += 1
                continue

            if validate_ili_exists(ili):
                valid_ili += 1
                if pos and validate_pos_match(ili, pos):
                    pos_match += 1
                elif pos:
                    pos_mismatch += 1
            else:
                invalid_ili += 1
                invalid_ids.append({"record": i, "span": ann.get("span"), "ili": ili})

    print(f"\n=== Validation Results ===")
    print(f"Total annotations: {total_annotations}")
    print(f"Valid ILI IDs:     {valid_ili} ({valid_ili/max(total_annotations,1)*100:.1f}%)")
    print(f"Invalid ILI IDs:   {invalid_ili} ({invalid_ili/max(total_annotations,1)*100:.1f}%)")
    print(f"POS matches:       {pos_match} ({pos_match/max(valid_ili,1)*100:.1f}% of valid)")
    print(f"POS mismatches:    {pos_mismatch}")

    if invalid_ids:
        print(f"\nInvalid ILI IDs (first 10):")
        for inv in invalid_ids[:10]:
            print(f"  record {inv['record']}: '{inv['span']}' -> ILI {inv['ili']}")

    # Golden comparison
    if golden_path:
        golden = json.loads(Path(golden_path).read_text())
        golden_examples = golden.get("examples", golden.get("pairs", []))

        if golden_examples:
            matches = 0
            total_golden = 0
            for ge in golden_examples:
                golden_annotations = ge.get("annotations", ge.get("ili_annotations", []))
                for ga in golden_annotations:
                    total_golden += 1
                    golden_ili = ga.get("ili")
                    golden_span = ga.get("span", "").lower()

                    # Find matching span in our results
                    for record in records:
                        for ann in record.get("annotations", []):
                            if ann.get("span", "").lower() == golden_span and ann.get("ili") == golden_ili:
                                matches += 1
                                break

            accuracy = matches / max(total_golden, 1) * 100
            print(f"\n=== Golden Comparison ===")
            print(f"Golden examples: {total_golden}")
            print(f"Matches:         {matches} ({accuracy:.1f}%)")
            threshold = 80.0
            if accuracy >= threshold:
                print(f"PASS: accuracy {accuracy:.1f}% >= {threshold}% threshold")
            else:
                print(f"FAIL: accuracy {accuracy:.1f}% < {threshold}% threshold")

    # Exit code
    if strict and invalid_ili > 0:
        print(f"\nSTRICT MODE: {invalid_ili} invalid ILI IDs found, exiting with error")
        sys.exit(1)

    if invalid_ili / max(total_annotations, 1) > 0.2:
        print(f"\nWARNING: >20% invalid ILI IDs — check your annotation pipeline")
        sys.exit(1)

    print(f"\nValidation PASSED")


def main():
    parser = argparse.ArgumentParser(description="Validate ILI annotations")
    parser.add_argument("input", help="JSONL file with ILI annotations")
    parser.add_argument("--golden", help="Golden examples JSON for accuracy comparison")
    parser.add_argument("--strict", action="store_true", help="Fail on any invalid ILI")
    args = parser.parse_args()
    validate_file(args.input, args.golden, args.strict)


if __name__ == "__main__":
    main()
