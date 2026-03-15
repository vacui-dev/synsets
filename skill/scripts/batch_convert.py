#!/usr/bin/env python3
"""
Batch Convert — convert plaintext to ILI-annotated format.

Processes text line-by-line (or paragraph-by-paragraph) and outputs JSONL
with ILI annotations for every content word.

Usage:
    python batch_convert.py input.txt --output output.jsonl
    python batch_convert.py input.txt --format inline  # annotated text only
    cat input.txt | python batch_convert.py - --output output.jsonl
"""

import argparse
import json
import re
import sys
from pathlib import Path

from ili_lookup import lookup_best, ensure_wordnet

# Words to skip (function words, determiners, etc.)
SKIP_WORDS = {
    # Determiners
    "the", "a", "an", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each", "all",
    # Pronouns
    "i", "me", "you", "he", "him", "she", "it", "we", "us", "they", "them",
    "myself", "yourself", "himself", "herself", "itself", "ourselves", "themselves",
    "who", "whom", "whose", "which", "what", "that",
    # Prepositions
    "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "over", "up", "down", "out", "off", "near",
    # Conjunctions
    "and", "but", "or", "nor", "so", "yet", "for", "both", "either",
    "neither", "not", "only", "whether", "if", "then", "than", "when",
    "while", "although", "because", "since", "unless", "until",
    # Auxiliaries / modals
    "is", "am", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should", "may", "might", "can", "could", "must",
    # Other function words
    "as", "very", "too", "also", "just", "even", "still", "already",
    "here", "there", "where", "how", "why", "more", "most", "much",
    "many", "such", "own", "other", "another",
}

# POS guessing heuristics for simple cases
VERB_SUFFIXES = ("ed", "ing", "ize", "ise", "ate", "ify")
ADJ_SUFFIXES = ("ful", "less", "ous", "ive", "able", "ible", "ical", "al")
ADV_SUFFIXES = ("ly",)
NOUN_SUFFIXES = ("tion", "sion", "ment", "ness", "ity", "ance", "ence", "er", "or")


def guess_pos(word: str) -> str | None:
    """Simple POS guesser based on suffixes. Returns n/v/a/r or None."""
    w = word.lower()
    if any(w.endswith(s) for s in ADV_SUFFIXES) and len(w) > 4:
        return "r"
    if any(w.endswith(s) for s in VERB_SUFFIXES) and len(w) > 4:
        return "v"
    if any(w.endswith(s) for s in ADJ_SUFFIXES) and len(w) > 4:
        return "a"
    if any(w.endswith(s) for s in NOUN_SUFFIXES) and len(w) > 4:
        return "n"
    return None


def simple_lemmatize(word: str) -> str:
    """Very basic lemmatization for common inflections."""
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    return w


def annotate_text(text: str) -> dict:
    """
    Annotate a text string with ILI tokens.

    Returns a dict with:
      - text: original text
      - annotated: text with ILI tokens replacing content words
      - annotations: list of {span, ili, pos, gloss} dicts
      - ili_vocab: set of unique ILI IDs used
    """
    # Split into word tokens, preserving punctuation boundaries
    tokens = re.findall(r"[\w']+|[^\w\s]", text)
    annotated_tokens = []
    annotations = []
    ili_vocab = set()

    for token in tokens:
        # Skip punctuation
        if not token[0].isalpha():
            annotated_tokens.append(token)
            continue

        word_lower = token.lower()

        # Skip function words
        if word_lower in SKIP_WORDS:
            annotated_tokens.append(token)
            continue

        # Try to look up the word
        pos_guess = guess_pos(word_lower)
        result = lookup_best(word_lower, pos=pos_guess)

        # If not found, try lemmatized form
        if result is None:
            lemma = simple_lemmatize(word_lower)
            if lemma != word_lower:
                result = lookup_best(lemma, pos=pos_guess)

        # If still not found, try without POS filter
        if result is None:
            result = lookup_best(word_lower)
            if result is None:
                lemma = simple_lemmatize(word_lower)
                if lemma != word_lower:
                    result = lookup_best(lemma)

        if result is not None:
            ili_token = result["ili_token"]
            annotated_tokens.append(ili_token)
            annotations.append({
                "span": token,
                "ili": result["ili"],
                "pos": result["pos"],
                "gloss": result["definition"],
            })
            ili_vocab.add(result["ili"])
        else:
            # Keep original word if no ILI mapping found
            annotated_tokens.append(token)

    # Reconstruct text with proper spacing
    annotated = ""
    for i, tok in enumerate(annotated_tokens):
        if i > 0 and tok not in ".,;:!?)" and annotated_tokens[i-1] not in "(":
            annotated += " "
        annotated += tok

    return {
        "text": text,
        "annotated": annotated,
        "annotations": annotations,
        "ili_vocab": sorted(ili_vocab),
    }


def process_file(input_path: str, output_path: str | None = None, fmt: str = "jsonl"):
    """Process an input file and write annotated output."""
    ensure_wordnet()

    if input_path == "-":
        lines = sys.stdin.read().strip().split("\n")
    else:
        lines = Path(input_path).read_text().strip().split("\n")

    # Filter empty lines
    lines = [l.strip() for l in lines if l.strip()]

    all_ili = set()
    results = []

    for i, line in enumerate(lines):
        result = annotate_text(line)
        all_ili.update(result["ili_vocab"])
        results.append(result)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(lines)} lines, {len(all_ili)} unique ILI concepts", file=sys.stderr)

    print(f"Done: {len(lines)} lines, {len(all_ili)} unique ILI concepts, {sum(len(r['annotations']) for r in results)} annotations", file=sys.stderr)

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
    elif fmt == "inline":
        out = sys.stdout if output_path is None else open(output_path, "w")
        for r in results:
            out.write(r["annotated"] + "\n")
        if output_path:
            out.close()
    elif fmt == "dataset":
        # Full dataset format with metadata
        dataset = {
            "format": "ili-sidecar-v1",
            "description": "Text-to-ILI concept annotation pairs",
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
    parser = argparse.ArgumentParser(description="Batch convert text to ILI-annotated format")
    parser.add_argument("input", help="Input text file (one sentence/paragraph per line, or - for stdin)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--format", "-f", choices=["jsonl", "inline", "dataset"], default="jsonl",
                        help="Output format: jsonl (annotation records), inline (annotated text only), dataset (full JSON dataset)")
    args = parser.parse_args()
    process_file(args.input, args.output, args.format)


if __name__ == "__main__":
    main()
