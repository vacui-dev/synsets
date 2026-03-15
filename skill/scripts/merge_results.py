#!/usr/bin/env python3
"""
Merge all batch annotation results into a single deduplicated file.

Reads all data/retranslated_batch_*.jsonl and data/retranslated_merged.jsonl,
deduplicates by record_num (keeps latest), sorts, and writes:
  - data/synsets_annotated.jsonl  (one record per line, human-readable)
  - data/stats.json              (summary statistics)

Post-processing:
  - Converts original_text from ILI-token form back to human-readable English
    by looking up each <|iNNNNN|> in WordNet and replacing with its first lemma.
  - Tracks which ILIs were pre-existing (from confidence-based pre-processing)
    vs. newly assigned by Hermes tool calls.

Safe to re-run (idempotent).
"""

import glob
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data")
WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")

INPUT_PATTERNS = [
    os.path.join(DATA_DIR, "retranslated_merged.jsonl"),
    os.path.join(DATA_DIR, "retranslated_batch_*.jsonl"),
]
OUTPUT_FILE = os.path.join(DATA_DIR, "synsets_annotated.jsonl")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")

ILI_RE = re.compile(r"<\|i(\d+)\|>")


def build_ili_word_cache(conn, ili_ids):
    """Batch-lookup ILI IDs to their first lemma form."""
    cache = {}
    for ili_id in ili_ids:
        ili_str = f"i{ili_id}"
        rows = conn.execute("""
            SELECT DISTINCT f.form
            FROM ilis i
            JOIN synsets sy ON sy.ili_rowid = i.rowid
            JOIN senses s ON s.synset_rowid = sy.rowid
            JOIN entries e ON s.entry_rowid = e.rowid
            JOIN forms f ON f.entry_rowid = e.rowid
            WHERE i.id = ?
            ORDER BY s.entry_rank LIMIT 1
        """, [ili_str]).fetchall()
        if rows:
            cache[ili_id] = rows[0][0]
        else:
            cache[ili_id] = f"[i{ili_id}]"
    return cache


def deili(text, cache):
    """Replace all <|iNNNNN|> tokens with human-readable words."""
    def replacer(m):
        ili_num = int(m.group(1))
        return cache.get(ili_num, f"[i{ili_num}]")
    return ILI_RE.sub(replacer, text)


def main():
    # Load records
    records = {}
    for pattern in INPUT_PATTERNS:
        for path in sorted(glob.glob(pattern)):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        rn = record.get("record_num")
                        if rn is not None:
                            records[rn] = record
                    except json.JSONDecodeError:
                        pass

    sorted_records = sorted(records.values(), key=lambda r: r["record_num"])

    if not sorted_records:
        print("No records found.")
        return

    # Collect ALL ILI IDs that appear in original_text and retranslated_text
    all_ili_ids = set()
    for r in sorted_records:
        for field in ("original_text", "retranslated_text"):
            text = r.get(field, "")
            all_ili_ids.update(int(m) for m in ILI_RE.findall(text))

    # Build word cache from WordNet
    print(f"Looking up {len(all_ili_ids)} unique ILI IDs in WordNet...")
    conn = sqlite3.connect(WORDNET_DB)
    conn.row_factory = sqlite3.Row
    cache = build_ili_word_cache(conn, all_ili_ids)
    conn.close()
    print(f"  Resolved {sum(1 for v in cache.values() if not v.startswith('['))}/{len(all_ili_ids)} to words")

    # Post-process each record
    total_assignments = 0
    unique_ilis = set()
    total_preexisting = 0
    total_hermes = 0

    for r in sorted_records:
        original = r.get("original_text", "")
        retranslated = r.get("retranslated_text", "")
        assignments = r.get("assignments", [])

        # ILIs that were already in original_text (from confidence-based method)
        preexisting_ilis = set(int(m) for m in ILI_RE.findall(original))
        # ILIs assigned by Hermes (in assignments list)
        hermes_ilis = set(a["ili"] for a in assignments)

        total_preexisting += len(preexisting_ilis)
        total_hermes += len(hermes_ilis)
        total_assignments += len(assignments)
        unique_ilis.update(preexisting_ilis | hermes_ilis)

        # Convert original_text to human-readable
        r["human_text"] = deili(original, cache)
        # Convert retranslated_text to human-readable (keeping both forms)
        r["human_annotated"] = deili(retranslated, cache)
        # Store counts
        r["preexisting_ili_count"] = len(preexisting_ilis)
        r["hermes_ili_count"] = len(hermes_ilis)

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        for record in sorted_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    n = len(sorted_records)
    stats = {
        "total_records": n,
        "total_assignments_by_hermes": total_hermes,
        "total_preexisting_ili": total_preexisting,
        "unique_ili_ids": len(unique_ilis),
        "avg_assignments_per_record": round(total_assignments / n, 1),
        "avg_preexisting_per_record": round(total_preexisting / n, 1),
        "avg_hermes_per_record": round(total_hermes / n, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
        f.write("\n")

    # Summary
    print(f"\nMerged {n} records from {len(glob.glob(INPUT_PATTERNS[1]))+1} files")
    print(f"  Pre-existing ILIs (confidence method): {total_preexisting:,} ({total_preexisting/n:.1f}/record)")
    print(f"  Hermes tool-call ILIs:                 {total_hermes:,} ({total_hermes/n:.1f}/record)")
    print(f"  Unique ILI concepts:                   {len(unique_ilis):,}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Stats:  {STATS_FILE}")


if __name__ == "__main__":
    main()
