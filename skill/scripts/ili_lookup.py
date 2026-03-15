#!/usr/bin/env python3
"""
ILI Lookup — resolve words to Interlingual Index concept IDs via WordNet.

Usage:
    python ili_lookup.py "dog" --pos n
    python ili_lookup.py "chase" --pos v
    python ili_lookup.py "happy" --pos a
    python ili_lookup.py "quickly" --pos r
    python ili_lookup.py "bank" --context "I deposited money at the bank"
"""

import argparse
import json
import sys

try:
    import wn
except ImportError:
    print("ERROR: 'wn' package not installed. Run: pip install wn", file=sys.stderr)
    print("Then download English WordNet: python -c \"import wn; wn.download('ewn:2020')\"", file=sys.stderr)
    sys.exit(1)


# POS mapping: user-friendly tags to WordNet POS codes
POS_MAP = {
    "n": "n",    # noun
    "v": "v",    # verb
    "a": "a",    # adjective
    "r": "r",    # adverb
    "s": "a",    # satellite adjective -> adjective
}


def ensure_wordnet():
    """Ensure English WordNet is downloaded."""
    try:
        en = wn.lexicons(lang="en")
        if not en:
            raise wn.Error("No English lexicon")
    except Exception:
        print("Downloading English WordNet (ewn:2020)...", file=sys.stderr)
        wn.download("ewn:2020")


def get_ili_id(synset) -> int | None:
    """Extract the ILI ID as an integer from a WordNet synset."""
    ili = synset.ili
    if not ili:
        return None
    # ili is a string like 'i46360'
    if isinstance(ili, str) and ili.startswith("i"):
        return int(ili[1:])
    return None


def lookup_word(word: str, pos: str | None = None, context: str | None = None) -> list[dict]:
    """
    Look up all senses of a word, optionally filtered by POS.

    Returns a list of dicts with: ili, pos, lemma, definition, synset_id
    """
    ensure_wordnet()

    results = []
    kwargs = {"lang": "en"}
    if pos and pos in POS_MAP:
        kwargs["pos"] = POS_MAP[pos]

    for sense in wn.senses(word, **kwargs):
        ss = sense.synset()
        ili_id = get_ili_id(ss)
        if ili_id is None:
            continue

        results.append({
            "word": word,
            "ili": ili_id,
            "ili_token": f"<|ILI_{ili_id:06d}|>",
            "pos": ss.pos,
            "definition": ss.definition(),
            "synset_id": ss.id,
            "lemmas": ss.lemmas(),
        })

    # Sort by ILI ID for deterministic output
    results.sort(key=lambda x: x["ili"])
    return results


def lookup_best(word: str, pos: str | None = None, context: str | None = None) -> dict | None:
    """
    Return the best (most common) sense for a word.

    WordNet lists senses in frequency order, so the first match is typically
    the most common sense. If context is provided, a smarter disambiguation
    could be added here.
    """
    ensure_wordnet()

    kwargs = {"lang": "en"}
    if pos and pos in POS_MAP:
        kwargs["pos"] = POS_MAP[pos]

    for sense in wn.senses(word, **kwargs):
        ss = sense.synset()
        ili_id = get_ili_id(ss)
        if ili_id is not None:
            return {
                "word": word,
                "ili": ili_id,
                "ili_token": f"<|ILI_{ili_id:06d}|>",
                "pos": ss.pos,
                "definition": ss.definition(),
                "synset_id": ss.id,
            }
    return None


def main():
    parser = argparse.ArgumentParser(description="Look up ILI concept IDs for words")
    parser.add_argument("word", help="Word to look up")
    parser.add_argument("--pos", choices=["n", "v", "a", "r", "s"], help="Part of speech filter")
    parser.add_argument("--context", help="Context sentence for disambiguation")
    parser.add_argument("--all", action="store_true", help="Show all senses (default: best match only)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.all:
        results = lookup_word(args.word, pos=args.pos, context=args.context)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print(f"No ILI entries found for '{args.word}'")
                sys.exit(1)
            for r in results:
                print(f"  {r['ili_token']}  {r['pos']}  {r['definition']}")
                print(f"    lemmas: {', '.join(r['lemmas'])}")
    else:
        result = lookup_best(args.word, pos=args.pos, context=args.context)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result is None:
                print(f"No ILI entry found for '{args.word}'")
                sys.exit(1)
            print(f"{result['ili_token']}  ({result['pos']})  {result['definition']}")


if __name__ == "__main__":
    main()
