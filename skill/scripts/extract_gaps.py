#!/usr/bin/env python3
"""Extract plaintext content words from gaps in ILI-annotated text.

Takes ONE record from the converted corpus and outputs content words
with surrounding context, ready to send to Hermes for ILI assignment.

This script does orchestration. Hermes does intelligence.
"""

import json
import re
import sys

# Hardcoded function word list — no external NLP libraries
FUNCTION_WORDS = {
    # articles
    'a', 'an', 'the',
    # prepositions
    'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'under', 'over', 'out', 'off', 'down', 'near', 'against', 'along', 'within',
    'without', 'beyond', 'across', 'around', 'toward', 'towards', 'upon',
    # conjunctions
    'and', 'but', 'or', 'nor', 'so', 'yet', 'for', 'either', 'neither',
    'both', 'whether', 'while', 'although', 'though', 'because', 'since',
    'unless', 'until', 'if', 'when', 'where', 'whereas', 'whenever',
    # pronouns
    'i', 'me', 'my', 'mine', 'myself',
    'you', 'your', 'yours', 'yourself',
    'he', 'him', 'his', 'himself',
    'she', 'her', 'hers', 'herself',
    'it', 'its', 'itself',
    'we', 'us', 'our', 'ours', 'ourselves',
    'they', 'them', 'their', 'theirs', 'themselves',
    'who', 'whom', 'whose', 'which', 'that', 'this', 'these', 'those',
    'what', 'whatever', 'whichever', 'whoever',
    # auxiliaries / modals
    'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing', 'done',
    'will', 'would', 'shall', 'should', 'may', 'might', 'can', 'could', 'must',
    # other function words
    'not', 'no', 'yes', 'very', 'too', 'also', 'just', 'only', 'even',
    'still', 'already', 'ever', 'never', 'always', 'often', 'sometimes',
    'here', 'there', 'then', 'now', 'how', 'why', 'all', 'each', 'every',
    'any', 'some', 'such', 'more', 'most', 'other', 'than', 'as', 'like',
    'well', 'much', 'many', 'few', 'less', 'least', 'own', 'same',
    'so', 'quite', 'rather', 'else', 'thus', 'hence', 'therefore',
}

# Pattern to match ILI tokens like <|i12345|>
ILI_TOKEN = re.compile(r'<\|i\d+\|>')


def extract_content_words(text):
    """Extract content words from gaps between ILI tokens, with context."""
    # Split text into segments: alternating between ILI tokens and plaintext
    parts = ILI_TOKEN.split(text)
    ili_tokens = ILI_TOKEN.findall(text)

    # Build a flat word list for context extraction
    all_words = []
    for part in parts:
        words = re.findall(r"[a-zA-Z'-]+", part)
        all_words.extend(words)

    # Now extract content words with position and context
    results = []
    seen = set()  # track unique words (case-folded)

    word_idx = 0
    for part in parts:
        words_in_part = re.findall(r"[a-zA-Z'-]+", part)
        for w in words_in_part:
            w_lower = w.lower().strip("'-")
            if not w_lower or len(w_lower) < 2:
                word_idx += 1
                continue
            if w_lower in FUNCTION_WORDS:
                word_idx += 1
                continue
            if w_lower in seen:
                word_idx += 1
                continue

            # Get context: 7 words before and after in the all_words list
            ctx_start = max(0, word_idx - 7)
            ctx_end = min(len(all_words), word_idx + 8)
            context = ' '.join(all_words[ctx_start:ctx_end])

            results.append({
                'word': w,
                'word_lower': w_lower,
                'context': context,
                'position': word_idx,
            })
            seen.add(w_lower)
            word_idx += 1

    return results


def main():
    corpus_path = sys.argv[1] if len(sys.argv) > 1 else 'data/synset_corpus_v4_converted_full.jsonl'
    record_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    with open(corpus_path) as f:
        for i, line in enumerate(f):
            if i == record_idx:
                rec = json.loads(line)
                break

    text = rec['text']
    source_ili = rec.get('source_ili', '?')

    # Count existing ILI tokens
    existing_ilis = ILI_TOKEN.findall(text)

    # Extract content words from gaps
    content_words = extract_content_words(text)

    # Count total non-function words in gaps (including duplicates)
    parts = ILI_TOKEN.split(text)
    total_gap_words = 0
    for part in parts:
        words = re.findall(r"[a-zA-Z'-]+", part)
        for w in words:
            w_lower = w.lower().strip("'-")
            if w_lower and len(w_lower) >= 2 and w_lower not in FUNCTION_WORDS:
                total_gap_words += 1

    print(f"=== Record #{record_idx} (source ILI: {source_ili}) ===")
    print(f"Text length: {len(text)} chars")
    print(f"Existing ILI tokens: {len(existing_ilis)}")
    print(f"Total content words in gaps: {total_gap_words}")
    print(f"Unique content words: {len(content_words)}")
    print(f"Current coverage: {len(existing_ilis)}/{len(existing_ilis)+total_gap_words} = {len(existing_ilis)*100/(len(existing_ilis)+total_gap_words):.1f}%")
    print()

    # Output for Hermes
    print("=== CONTENT WORDS FOR HERMES ===")
    for i, cw in enumerate(content_words, 1):
        print(f'{i}. "{cw["word"]}" — context: "...{cw["context"]}..."')

    # Also dump as JSON for programmatic use
    with open('/tmp/gap_words_record0.json', 'w') as f:
        json.dump({
            'source_ili': source_ili,
            'record_idx': record_idx,
            'existing_ili_count': len(existing_ilis),
            'total_gap_content_words': total_gap_words,
            'unique_content_words': len(content_words),
            'words': content_words,
        }, f, indent=2)
    print(f"\nJSON written to /tmp/gap_words_record0.json")


if __name__ == '__main__':
    main()
