#!/usr/bin/env python3
"""
Hermes Annotate — use Nous Hermes API for accurate ILI annotation.

Uses Hermes-4-405B for word sense disambiguation, then resolves lemmas
to ILI IDs via WordNet. This produces much more accurate annotations than
naive POS guessing because Hermes understands context.

Usage:
    python hermes_annotate.py "The dog chased the cat up the tree"
    python hermes_annotate.py --batch input.txt -o output.jsonl
    python hermes_annotate.py --batch input.txt -f dataset -o dataset.json
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from ili_lookup import lookup_best, lookup_word, ensure_wordnet

# Load API key from .env file
def load_api_key() -> str:
    """Load API key from .env file or environment variable."""
    # Check environment variable first
    key = os.environ.get("NOUS_API_KEY")
    if key:
        return key

    # Check .env file in repo root
    env_paths = [
        Path(__file__).parent.parent.parent / ".env",  # ili-annotator/.env
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text().strip().split("\n"):
                line = line.strip()
                if line.startswith("NOUS_API_KEY="):
                    return line.split("=", 1)[1].strip()

    print("ERROR: No API key found. Set NOUS_API_KEY env var or create .env file.", file=sys.stderr)
    sys.exit(1)


API_BASE = "https://inference-api.nousresearch.com/v1"
MODEL = "Hermes-4-405B"

SYSTEM_PROMPT = """You are an ILI (Interlingual Index) annotation assistant. Your job is to identify content words in a sentence and provide their part of speech and lemma (base dictionary form).

Rules:
1. Annotate ONLY content words: nouns, verbs, adjectives, adverbs
2. SKIP function words: determiners (the, a, an), prepositions (in, on, at, to, for, with, by, from, of, up, down, over, under, about, into, through, before, after, between, near), conjunctions (and, but, or, nor, so, yet), pronouns (I, me, you, he, she, it, we, they, him, her, us, them, who, which, that), auxiliaries (is, am, are, was, were, be, been, being, has, have, had, do, does, did, will, would, shall, should, may, might, can, could, must)
3. For verbs, the lemma is the infinitive: "chased" -> "chase", "running" -> "run", "ate" -> "eat"
4. For nouns, the lemma is the singular: "dogs" -> "dog", "children" -> "child"
5. For adjectives/adverbs, the lemma is the base form: "quickly" -> "quickly", "better" -> "good"
6. POS tags: n=noun, v=verb, a=adjective, r=adverb

Return ONLY a JSON array. No explanation, no markdown, no wrapping. Example:
[{"span": "dog", "pos": "n", "lemma": "dog"}, {"span": "chased", "pos": "v", "lemma": "chase"}]"""


def call_hermes(text: str, api_key: str, max_retries: int = 3) -> list[dict]:
    """Call Hermes API to get content word annotations for a text."""
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            content = result["choices"][0]["message"]["content"].strip()
            # Parse JSON from response (handle potential markdown wrapping)
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            annotations = json.loads(content)
            if isinstance(annotations, list):
                return annotations
            else:
                print(f"  WARNING: Hermes returned non-list: {type(annotations)}", file=sys.stderr)
                return []

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            elif e.code == 402:
                print("ERROR: Out of API credits!", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"  HTTP error {e.code}: {e.read().decode()}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return []
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  Parse error: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return []
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return []

    return []


def annotate_with_hermes(text: str, api_key: str) -> dict:
    """
    Annotate text using Hermes for WSD, then resolve lemmas to ILI IDs via WordNet.
    """
    # Step 1: Get content word annotations from Hermes
    hermes_annotations = call_hermes(text, api_key)

    if not hermes_annotations:
        return {"text": text, "annotated": text, "annotations": [], "ili_vocab": []}

    # Step 2: Resolve each lemma to ILI ID via WordNet
    annotations = []
    ili_vocab = set()
    token_replacements = []  # (span, ili_token) pairs for building annotated text

    for ann in hermes_annotations:
        span = ann.get("span", "")
        pos = ann.get("pos", "")
        lemma = ann.get("lemma", span)

        if not span or not lemma:
            continue

        # Look up the lemma in WordNet with POS filter
        result = lookup_best(lemma, pos=pos)

        # If not found with POS, try without
        if result is None:
            result = lookup_best(lemma)

        # If still not found, try the original span
        if result is None and span.lower() != lemma.lower():
            result = lookup_best(span.lower(), pos=pos)
            if result is None:
                result = lookup_best(span.lower())

        if result is not None:
            annotations.append({
                "span": span,
                "ili": result["ili"],
                "pos": result["pos"],
                "gloss": result["definition"],
            })
            ili_vocab.add(result["ili"])
            token_replacements.append((span, result["ili_token"]))
        # else: word stays as plain text (proper noun, slang, etc.)

    # Step 3: Build annotated text by replacing spans
    annotated = text
    # Replace in reverse order of position to preserve indices
    for span, ili_token in reversed(token_replacements):
        # Find the span in the text (case-insensitive first match not yet replaced)
        import re
        pattern = re.compile(re.escape(span), re.IGNORECASE)
        annotated = pattern.sub(ili_token, annotated, count=1)

    return {
        "text": text,
        "annotated": annotated,
        "annotations": annotations,
        "ili_vocab": sorted(ili_vocab),
    }


def process_single(text: str, api_key: str):
    """Process a single text and print results."""
    ensure_wordnet()
    result = annotate_with_hermes(text, api_key)

    print(f"Text:      {result['text']}")
    print(f"Annotated: {result['annotated']}")
    print(f"ILI vocab: {len(result['ili_vocab'])} concepts")
    for ann in result["annotations"]:
        print(f"  {ann['span']:15s} -> <|ILI_{ann['ili']:06d}|>  ({ann['pos']})  {ann['gloss'][:60]}")


def process_batch(input_path: str, output_path: str | None, fmt: str, api_key: str,
                  max_lines: int = 0, delay: float = 0.5):
    """Process a file of texts line by line."""
    ensure_wordnet()

    if input_path == "-":
        lines = sys.stdin.read().strip().split("\n")
    else:
        lines = Path(input_path).read_text().strip().split("\n")

    lines = [l.strip() for l in lines if l.strip()]

    if max_lines > 0:
        lines = lines[:max_lines]

    all_ili = set()
    results = []
    total_tokens = 0

    print(f"Processing {len(lines)} lines with Hermes-4-405B...", file=sys.stderr)

    for i, line in enumerate(lines):
        result = annotate_with_hermes(line, api_key)
        all_ili.update(result["ili_vocab"])
        results.append(result)
        total_tokens += len(result["annotations"])

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(lines)}] {len(all_ili)} unique ILIs, {total_tokens} total annotations", file=sys.stderr)

        # Rate limiting delay
        if delay > 0 and i < len(lines) - 1:
            time.sleep(delay)

    print(f"Done: {len(lines)} lines, {len(all_ili)} unique ILIs, {total_tokens} annotations", file=sys.stderr)

    # Write output
    if fmt == "jsonl":
        out = sys.stdout if output_path is None else open(output_path, "w")
        for r in results:
            json.dump({
                "text": r["text"],
                "annotated": r["annotated"],
                "annotations": r["annotations"],
            }, out)
            out.write("\n")
        if output_path:
            out.close()
            print(f"Written to {output_path}", file=sys.stderr)

    elif fmt == "dataset":
        dataset = {
            "format": "ili-sidecar-v1",
            "description": "Text-to-ILI concept annotations generated by Hermes-4-405B with WordNet ILI resolution",
            "model": MODEL,
            "ili_vocab_size": len(all_ili),
            "num_pairs": len(results),
            "pairs": [
                {
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
            print(f"Written dataset to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Annotate text with ILI concepts using Hermes-4-405B")
    parser.add_argument("text", nargs="?", help="Single text to annotate (or use --batch)")
    parser.add_argument("--batch", help="Input file for batch processing (one sentence per line, or - for stdin)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--format", "-f", choices=["jsonl", "dataset"], default="jsonl")
    parser.add_argument("--max", type=int, default=0, help="Max lines to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls in seconds")
    args = parser.parse_args()

    api_key = load_api_key()

    if args.batch:
        process_batch(args.batch, args.output, args.format, api_key, args.max, args.delay)
    elif args.text:
        process_single(args.text, api_key)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
