#!/usr/bin/env python3
"""Send content words to Hermes for ILI disambiguation.

This is the core intelligence layer. Gap words are extracted locally,
Hermes assigns the correct WordNet ILI to each one using contextual
understanding. No spaCy, no NLTK — Hermes IS the disambiguation engine.
"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.parent  # ili-annotator root
ENV_FILE = SCRIPT_DIR / ".env"


def load_api_key():
    if os.environ.get("NOUS_API_KEY"):
        return os.environ["NOUS_API_KEY"]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("NOUS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key", file=sys.stderr)
    sys.exit(1)


def call_hermes(system_prompt, user_message, timeout=30):
    """Single focused call to Hermes API."""
    import urllib.request

    api_key = load_api_key()
    payload = json.dumps({
        "model": "Hermes-4-405B",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 4096,
        "temperature": 0.3,  # lower temp for factual disambiguation
    }).encode()

    req = urllib.request.Request(
        "https://inference-api.nousresearch.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]


SYSTEM_PROMPT = """You are Hermes, a word sense disambiguation engine for the
Interlingual Index (ILI) system. ILI maps English words to WordNet synset
concept IDs — integer identifiers that are language-independent.

Your job: given a content word and its sentence context, return the correct
EXISTING WordNet ILI ID. Format: iNNNNN (the 'i' prefix + integer).

Rules:
1. Use ONLY existing WordNet ILI IDs. Do not invent new ones.
2. Pick the sense that best fits the CONTEXT, not just the most common sense.
3. If a word is an inflected form (e.g., "represents"), map to the base form's
   ILI (e.g., "represent").
4. Flag multi-word expressions that should be treated as one unit.
5. For each word, return: WORD -> iNNNNN (lemma, POS n/v/a/r, HIGH/MEDIUM/LOW)

You know WordNet well. You know that:
- ILI i35152 = "represent" (v) "take the place of or be parallel to"
- ILI i56 = "conceptual" (a) "being or characterized by concepts"
- ILI i75201 = "fundamental" (n) "any factor of importance"
- etc.

Be precise. Be contextual. This is what you're good at."""


def disambiguate_batch(words_with_context):
    """Send a batch of words to Hermes for disambiguation."""
    lines = []
    for i, item in enumerate(words_with_context, 1):
        lines.append(f'{i}. "{item["word"]}" — context: "{item["context"]}"')

    user_msg = f"""Disambiguate these {len(words_with_context)} content words.
For each, return the correct existing WordNet ILI ID based on context.

Format per line:
N. WORD -> iNNNNN (lemma, POS, confidence)

Words:
""" + "\n".join(lines)

    return call_hermes(SYSTEM_PROMPT, user_msg)


def main():
    gap_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gap_words_record0.json"

    with open(gap_file) as f:
        data = json.load(f)

    words = data["words"]
    print(f"Sending {len(words)} words to Hermes for disambiguation...")
    print(f"Source ILI: {data['source_ili']}, existing ILIs: {data['existing_ili_count']}")
    print()

    # Send in batches of 25 to avoid timeout
    batch_size = 25
    all_responses = []

    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(words) + batch_size - 1) // batch_size
        print(f"--- Batch {batch_num}/{total_batches} ({len(batch)} words) ---")

        try:
            response = disambiguate_batch(batch)
            print(response)
            print()
            all_responses.append(response)
        except Exception as e:
            print(f"ERROR on batch {batch_num}: {e}")
            all_responses.append(f"ERROR: {e}")

    # Save all responses
    output = {
        "source_ili": data["source_ili"],
        "record_idx": data["record_idx"],
        "batches": all_responses,
    }
    out_path = "/tmp/hermes_disambiguations_record0.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nAll responses saved to {out_path}")


if __name__ == "__main__":
    main()
