#!/usr/bin/env python3
"""
Convert Synset Corpus — transform synset definition files into ILI-annotated dataset.

The source data is a directory of text files, one per synset, where filenames are
ILI IDs (e.g., 10007.txt) and content uses <|iNNNN|> inline tokens.

This script:
1. Reads all synset definition files
2. Extracts inline ILI references (<|iNNNN|> tokens)
3. Normalizes to the <|ILI_NNNNNN|> format
4. Outputs in ili-sidecar-v1 format

Usage:
    python convert_synset_corpus.py /path/to/synset/dir -o dataset.json
    python convert_synset_corpus.py /path/to/synset/dir -f jsonl -o dataset.jsonl
    python convert_synset_corpus.py /path/to/synset/dir --max 1000 -o sample.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# Regex patterns for existing synset token formats
# Matches <|iNNNN|> and <|iNNNN:word|> formats
TOKEN_PATTERN = re.compile(r'<\|i(\d+)(?::([^|]*))?\|>')


def normalize_token(match) -> str:
    """Convert <|iNNNN|> or <|iNNNN:word|> to <|ILI_NNNNNN|> format."""
    ili_id = int(match.group(1))
    return f"<|ILI_{ili_id:06d}|>"


def extract_ili_ids(text: str) -> list[int]:
    """Extract all ILI IDs from a text containing <|iNNNN|> tokens."""
    return [int(m.group(1)) for m in TOKEN_PATTERN.finditer(text)]


def convert_file(filepath: Path) -> dict | None:
    """Convert a single synset file to annotation record."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        print(f"  SKIP {filepath.name}: {e}", file=sys.stderr)
        return None

    if not text:
        return None

    # Extract the synset ID from filename
    stem = filepath.stem
    # Handle _converted suffix
    if stem.endswith("_converted"):
        stem = stem[:-10]

    try:
        source_ili = int(stem)
    except ValueError:
        return None

    # Extract all ILI IDs used in the text
    ili_ids = extract_ili_ids(text)

    # Convert tokens to normalized format
    annotated = TOKEN_PATTERN.sub(normalize_token, text)

    # Build annotations list
    annotations = []
    seen = set()
    for m in TOKEN_PATTERN.finditer(text):
        ili_id = int(m.group(1))
        hint = m.group(2) or ""
        if ili_id not in seen:
            seen.add(ili_id)
            annotations.append({
                "ili": ili_id,
                "hint": hint,  # word hint from <|iNNNN:word|> format, if present
            })

    return {
        "source_ili": source_ili,
        "text": text,
        "annotated": annotated,
        "annotations": annotations,
        "ili_count": len(ili_ids),
        "unique_ili": len(seen),
    }


def convert_directory(input_dir: str, output_path: str | None = None,
                      fmt: str = "dataset", max_files: int = 0,
                      model_filter: str | None = None):
    """Convert a directory (or directory tree) of synset files."""
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"ERROR: {input_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Find all .txt files
    txt_files = sorted(input_path.rglob("*.txt"))
    if model_filter:
        txt_files = [f for f in txt_files if model_filter in str(f)]

    print(f"Found {len(txt_files)} text files in {input_dir}", file=sys.stderr)

    if max_files > 0:
        txt_files = txt_files[:max_files]
        print(f"Processing first {max_files} files", file=sys.stderr)

    results = []
    all_ili = set()
    skipped = 0

    for i, filepath in enumerate(txt_files):
        record = convert_file(filepath)
        if record is None:
            skipped += 1
            continue

        results.append(record)
        for ann in record["annotations"]:
            all_ili.add(ann["ili"])

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(txt_files)} files, {len(all_ili)} unique ILI concepts", file=sys.stderr)

    print(f"Done: {len(results)} records, {skipped} skipped, {len(all_ili)} unique ILI concepts", file=sys.stderr)

    # Write output
    if fmt == "dataset":
        dataset = {
            "format": "ili-sidecar-v1",
            "description": "ILI concept definitions with inline concept references",
            "ili_vocab_size": len(all_ili),
            "num_pairs": len(results),
            "pairs": [
                {
                    "source_ili": r["source_ili"],
                    "text": r["text"],
                    "annotated": r["annotated"],
                    "annotations": r["annotations"],
                }
                for r in results
            ],
        }
        out = sys.stdout if output_path is None else open(output_path, "w")
        json.dump(dataset, out, indent=2)
        out.write("\n")
        if output_path:
            out.close()
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Written dataset to {output_path} ({size_mb:.1f} MB)", file=sys.stderr)

    elif fmt == "jsonl":
        out = sys.stdout if output_path is None else open(output_path, "w")
        for r in results:
            json.dump({
                "source_ili": r["source_ili"],
                "text": r["text"],
                "annotated": r["annotated"],
                "annotations": r["annotations"],
            }, out)
            out.write("\n")
        if output_path:
            out.close()
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Written JSONL to {output_path} ({size_mb:.1f} MB)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Convert synset corpus to ILI-annotated dataset")
    parser.add_argument("input_dir", help="Directory containing synset .txt files")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--format", "-f", choices=["dataset", "jsonl"], default="dataset",
                        help="Output format")
    parser.add_argument("--max", type=int, default=0, help="Max files to process (0=all)")
    parser.add_argument("--model", help="Filter by model name (substring match on path)")
    args = parser.parse_args()
    convert_directory(args.input_dir, args.output, args.format, args.max, args.model)


if __name__ == "__main__":
    main()
