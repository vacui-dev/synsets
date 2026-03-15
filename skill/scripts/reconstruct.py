#!/usr/bin/env python3
"""
Reconstruct clean ILI-annotated text sentence by sentence.

Sends each sentence to Hermes individually with its ILI sense table,
showing previously completed sentences as context. This keeps Hermes's
attention focused on a small chunk at a time.

Output format: <|ILI_NNNNNN|>word for every ILI, fully readable text.

Usage:
    python3 skill/scripts/reconstruct.py --start 0 --count 50 --output data/clean_batch_0.jsonl
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data")
WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")
INPUT_FILE = os.path.join(DATA_DIR, "synsets_annotated.jsonl")

ENV_FILE = os.path.join(SCRIPT_DIR, "..", "..", ".env")
API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
MODEL = "Hermes-4-405B"

ILI_RE = re.compile(r"<\|(?:i|ILI_)(\d+)\|>")


def load_api_key() -> str:
    if os.environ.get("NOUS_API_KEY"):
        return os.environ["NOUS_API_KEY"]
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("NOUS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key", file=sys.stderr)
    sys.exit(1)


def call_hermes(messages: list[dict], max_tokens: int = 2048) -> str:
    api_key = load_api_key()
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.15,
        "reasoning": True,
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"]


def normalize_ili(text: str) -> str:
    """Convert <|iNNNNN|> to <|ILI_NNNNNN|> format."""
    def repl(m):
        return f"<|ILI_{int(m.group(1)):06d}|>"
    return ILI_RE.sub(repl, text)


def get_ili_word_forms(conn, ili_ids: set) -> dict:
    """Get word forms (up to 10) and definition for each ILI."""
    cache = {}
    for ili_id in ili_ids:
        ili_str = f"i{ili_id}"
        rows = conn.execute("""
            SELECT DISTINCT f.form
            FROM ilis i JOIN synsets sy ON sy.ili_rowid = i.rowid
            JOIN senses s ON s.synset_rowid = sy.rowid
            JOIN entries e ON s.entry_rowid = e.rowid
            JOIN forms f ON f.entry_rowid = e.rowid
            WHERE i.id = ? ORDER BY s.entry_rank LIMIT 10
        """, [ili_str]).fetchall()

        defn = conn.execute("""
            SELECT d.definition FROM ilis i
            JOIN synsets sy ON sy.ili_rowid = i.rowid
            JOIN definitions d ON d.synset_rowid = sy.rowid
            WHERE i.id = ? LIMIT 1
        """, [ili_str]).fetchone()

        cache[ili_id] = {
            "forms": [r[0] for r in rows] if rows else [],
            "definition": defn[0] if defn else "",
        }
    return cache


def split_sentences(text: str) -> list[str]:
    """Split text into sentences/chunks, preserving markdown headers."""
    # Split on sentence boundaries and paragraph breaks
    chunks = re.split(r'(?<=[.!?])\s+|\n\n+', text)
    # Keep headers attached to their following content
    result = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk:
            result.append(chunk)
    return result


def build_sentence_sense_table(sentence: str, ili_data: dict) -> str:
    """Build a compact sense table for just the ILIs in this sentence."""
    ili_ids = [int(m) for m in ILI_RE.findall(sentence)]
    lines = []
    seen = set()
    for ili_id in ili_ids:
        if ili_id in seen:
            continue
        seen.add(ili_id)
        data = ili_data.get(ili_id, {})
        forms = data.get("forms", [])[:10]
        defn = data.get("definition", "")[:80]
        tag = f"ILI_{ili_id:06d}"
        lines.append(f"  {tag}: [{', '.join(forms)}] — {defn}")
    return "\n".join(lines)


SENTENCE_PROMPT = """Reformat this ONE sentence. The ILI tags need to go BEFORE their word.

INPUT PATTERNS:
- "word <|ILI_N|>" means the tag belongs to that word. Output: <|ILI_N|>word (move tag before word, remove the duplicate)
- "<|ILI_N|>" alone means pick a word from the sense table. Output: <|ILI_N|>chosen_word

SENSE TABLE:
{sense_table}

{context}SENTENCE TO REFORMAT:
{sentence}

Output ONLY the reformatted sentence. Every <|ILI_NNNNNN|> tag must be followed by exactly one word. No duplicates."""


def reconstruct_sentence(sentence: str, ili_data: dict, prior_context: str) -> str:
    """Reconstruct one sentence with Hermes."""
    normalized = normalize_ili(sentence)
    sense_table = build_sentence_sense_table(normalized, ili_data)

    if not sense_table:
        # No ILIs in this sentence, return as-is
        return normalized

    context_block = ""
    if prior_context:
        # Show last ~500 chars of prior context for continuity
        ctx = prior_context[-500:]
        context_block = f"PRIOR CONTEXT (already done, for reference):\n{ctx}\n\n"

    prompt = SENTENCE_PROMPT.format(
        sense_table=sense_table,
        context=context_block,
        sentence=normalized,
    )

    messages = [{"role": "user", "content": prompt}]
    result = call_hermes(messages, max_tokens=2048)

    # Strip any markdown fences Hermes might wrap it in
    result = result.strip()
    if result.startswith("```"):
        lines = result.split("\n")
        result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return result.strip()


def reconstruct_record(record: dict, ili_data: dict) -> dict:
    """Reconstruct an entire record sentence by sentence."""
    retranslated = record.get("retranslated_text", "")
    sentences = split_sentences(retranslated)

    completed_parts = []
    total_hermes_calls = 0

    for i, sentence in enumerate(sentences):
        prior = "\n".join(completed_parts)

        # Check if this sentence has any ILI tags
        if ILI_RE.search(sentence):
            try:
                result = reconstruct_sentence(sentence, ili_data, prior)
                total_hermes_calls += 1
            except Exception as e:
                print(f"      sentence {i+1} error: {e}", file=sys.stderr)
                result = normalize_ili(sentence)
        else:
            result = sentence

        completed_parts.append(result)

    clean_text = "\n\n".join(completed_parts)
    ili_count = len(ILI_RE.findall(clean_text))

    return {
        "record_num": record["record_num"],
        "clean_text": clean_text,
        "ili_count": ili_count,
        "hermes_calls": total_hermes_calls,
        "hermes_count": record.get("hermes_ili_count", 0),
        "preexisting_count": record.get("preexisting_ili_count", 0),
    }


def main():
    parser = argparse.ArgumentParser(description="Reconstruct clean ILI-annotated text")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--output", "-o", default=os.path.join(DATA_DIR, "clean_batch_0.jsonl"))
    args = parser.parse_args()

    records = []
    with open(INPUT_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    subset = records[args.start:args.start + args.count]
    if not subset:
        print("No records to process.", file=sys.stderr)
        return

    print(f"Processing {len(subset)} records (index {args.start}..{args.start + len(subset) - 1})", file=sys.stderr)

    # Collect all ILI IDs
    all_ili_ids = set()
    for r in subset:
        for field in ("original_text", "retranslated_text"):
            all_ili_ids.update(int(m) for m in ILI_RE.findall(r.get(field, "")))

    print(f"Loading word forms for {len(all_ili_ids)} ILIs...", file=sys.stderr)
    conn = sqlite3.connect(WORDNET_DB)
    conn.row_factory = sqlite3.Row
    ili_data = get_ili_word_forms(conn, all_ili_ids)
    conn.close()

    results = []
    for i, record in enumerate(subset):
        rn = record["record_num"]
        sentences = split_sentences(record.get("retranslated_text", ""))
        print(f"  [{i+1}/{len(subset)}] Record #{rn}: {len(sentences)} sentences...", file=sys.stderr)

        result = reconstruct_record(record, ili_data)
        results.append(result)

        print(f"           → {result['ili_count']} ILIs, {result['hermes_calls']} Hermes calls", file=sys.stderr)

        # Incremental save
        with open(args.output, "w") as f:
            for res in results:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print(f"\nDone: {len(results)} records", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
