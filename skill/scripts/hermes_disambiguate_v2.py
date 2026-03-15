#!/usr/bin/env python3
"""Hermes-powered ILI disambiguation with real WordNet candidates.

Pipeline:
1. Look up ALL WordNet synsets for each gap word (+ lemmatized forms)
2. Hermes picks the right sense from real candidates, given context
3. Assemble the result

No spaCy. No NLTK. Local DB lookup, Hermes does intelligence.
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.parent  # ili-annotator root
ENV_FILE = SCRIPT_DIR / ".env"
WN_DB = Path(os.path.expanduser("~/.wn_data/wn.db"))

# Function words to skip
FUNCTION_WORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'between', 'under', 'over', 'out', 'off', 'down',
    'near', 'against', 'along', 'within', 'without', 'beyond', 'across',
    'around', 'toward', 'towards', 'upon', 'and', 'but', 'or', 'nor', 'so',
    'yet', 'for', 'either', 'neither', 'both', 'whether', 'while',
    'although', 'though', 'because', 'since', 'unless', 'until', 'if',
    'when', 'where', 'whereas', 'whenever', 'i', 'me', 'my', 'mine',
    'myself', 'you', 'your', 'yours', 'yourself', 'he', 'him', 'his',
    'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
    'we', 'us', 'our', 'ours', 'ourselves', 'they', 'them', 'their',
    'theirs', 'themselves', 'who', 'whom', 'whose', 'which', 'that', 'this',
    'these', 'those', 'what', 'whatever', 'whichever', 'whoever', 'is',
    'am', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'having', 'do', 'does', 'did', 'doing', 'done', 'will', 'would',
    'shall', 'should', 'may', 'might', 'can', 'could', 'must', 'not', 'no',
    'yes', 'very', 'too', 'also', 'just', 'only', 'even', 'still',
    'already', 'ever', 'never', 'always', 'often', 'sometimes', 'here',
    'there', 'then', 'now', 'how', 'why', 'all', 'each', 'every', 'any',
    'some', 'such', 'more', 'most', 'other', 'than', 'as', 'like', 'well',
    'much', 'many', 'few', 'less', 'least', 'own', 'same', 'so', 'quite',
    'rather', 'else', 'thus', 'hence', 'therefore', 'something', 'nothing',
    'everything', 'anything',
}

ILI_TOKEN = re.compile(r'<\|i\d+\|>')

# Simple lemmatization rules (no NLTK needed)
LEMMA_RULES = [
    ('ies', 'y'), ('ies', 'ie'), ('ves', 'f'), ('ves', 'fe'),
    ('ses', 's'), ('ses', 'se'), ('xes', 'x'), ('zes', 'z'),
    ('ches', 'ch'), ('shes', 'sh'),
    ('ings', 'ing'), ('ings', ''),
    ('ing', 'e'), ('ing', ''),
    ('ness', ''), ('ment', ''), ('tion', 't'), ('tion', 'te'),
    ('sion', 'd'), ('sion', 'de'), ('ation', 'ate'), ('ation', 'e'),
    ('ical', 'ic'), ('ical', ''), ('ably', 'able'), ('ibly', 'ible'),
    ('ally', 'al'), ('ially', 'ial'), ('ously', 'ous'), ('ively', 'ive'),
    ('ness', ''), ('ment', ''),
    ('ful', ''), ('less', ''), ('able', ''), ('ible', ''),
    ('ity', 'e'), ('ity', ''),
    ('ly', ''), ('al', ''), ('ous', ''),
    ('ed', 'e'), ('ed', ''),
    ('er', 'e'), ('er', ''),
    ('est', 'e'), ('est', ''),
    ('es', 'e'), ('es', ''),
    ('s', ''),
]


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
    import urllib.request
    api_key = load_api_key()
    payload = json.dumps({
        "model": "Hermes-4-405B",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 4096,
        "temperature": 0.2,
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


def get_lemma_candidates(word):
    """Generate possible base forms of a word using suffix rules."""
    candidates = {word, word.lower()}
    w = word.lower()
    for suffix, replacement in LEMMA_RULES:
        if w.endswith(suffix) and len(w) > len(suffix) + 1:
            base = w[:-len(suffix)] + replacement
            if len(base) >= 2:
                candidates.add(base)
    return candidates


def lookup_wordnet_senses(word, db_conn):
    """Look up all WordNet synsets for a word and its lemmatized forms."""
    candidates = get_lemma_candidates(word)
    cursor = db_conn.cursor()

    senses = []
    seen_ilis = set()

    for candidate in candidates:
        # Query via forms -> entries -> senses -> synsets -> ilis
        cursor.execute("""
            SELECT DISTINCT i.id, s.pos, f.form, d.definition
            FROM forms f
            JOIN entries e ON e.rowid = f.entry_rowid
            JOIN senses se ON se.entry_rowid = e.rowid
            JOIN synsets s ON s.rowid = se.synset_rowid
            JOIN ilis i ON i.rowid = s.ili_rowid
            LEFT JOIN definitions d ON d.synset_rowid = s.rowid
            WHERE LOWER(f.form) = ?
            ORDER BY se.entry_rank
        """, (candidate.lower(),))

        for row in cursor.fetchall():
            ili_id, pos, form, definition = row
            if ili_id and ili_id not in seen_ilis:
                seen_ilis.add(ili_id)
                senses.append({
                    "ili": ili_id,
                    "pos": pos,
                    "lemma": form,
                    "definition": definition or "(no definition)",
                })

    return senses


def extract_gap_words(text):
    """Extract content words from gaps between ILI tokens."""
    parts = ILI_TOKEN.split(text)
    all_text_words = []
    for part in parts:
        words = re.findall(r"[a-zA-Z'-]+", part)
        all_text_words.extend(words)

    results = []
    seen = set()
    word_positions = []

    # Build full word list for context
    for part in parts:
        words = re.findall(r"[a-zA-Z'-]+", part)
        word_positions.extend(words)

    idx = 0
    for part in parts:
        words_in_part = re.findall(r"[a-zA-Z'-]+", part)
        for w in words_in_part:
            w_clean = w.lower().strip("'-")
            if not w_clean or len(w_clean) < 2 or w_clean in FUNCTION_WORDS:
                idx += 1
                continue
            if w_clean in seen:
                idx += 1
                continue

            ctx_start = max(0, idx - 7)
            ctx_end = min(len(word_positions), idx + 8)
            context = ' '.join(word_positions[ctx_start:ctx_end])

            results.append({
                'word': w,
                'word_lower': w_clean,
                'context': context,
                'position': idx,
            })
            seen.add(w_clean)
            idx += 1

    return results


SYSTEM_PROMPT = """You are Hermes, a word sense disambiguation engine.

For each word, you receive:
- The word as it appears in text
- Its surrounding context
- A list of REAL WordNet synset candidates with ILI IDs and definitions

Your job: pick the candidate that best fits the context. Return ONLY the
selected ILI ID and your confidence.

If NO candidate fits well, return "NONE".

Format your response as one line per word:
N. WORD -> ILI_ID (confidence: HIGH/MEDIUM/LOW)

Be precise. Use the definitions and context together to pick the right sense."""


def main():
    corpus_path = sys.argv[1] if len(sys.argv) > 1 else str(SCRIPT_DIR / "data" / "synset_corpus_v4_converted_full.jsonl")
    record_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    # Load record
    with open(corpus_path) as f:
        for i, line in enumerate(f):
            if i == record_idx:
                rec = json.loads(line)
                break

    text = rec['text']
    source_ili = rec.get('source_ili', '?')

    print(f"=== Record #{record_idx} (source ILI: {source_ili}) ===")

    # Extract gap words
    gap_words = extract_gap_words(text)
    existing_ilis = ILI_TOKEN.findall(text)

    print(f"Existing ILI tokens: {len(existing_ilis)}")
    print(f"Unique gap content words: {len(gap_words)}")

    # Look up WordNet candidates for each word
    db_conn = sqlite3.connect(str(WN_DB))

    words_with_candidates = []
    single_sense = []
    no_match = []

    for gw in gap_words:
        senses = lookup_wordnet_senses(gw['word'], db_conn)
        if len(senses) == 0:
            no_match.append(gw)
        elif len(senses) == 1:
            # Single sense: auto-assign, no disambiguation needed
            single_sense.append({**gw, 'assigned_ili': senses[0]['ili'], 'senses': senses})
        else:
            # Multi-sense: Hermes disambiguates
            words_with_candidates.append({**gw, 'senses': senses})

    print(f"\nSingle-sense (auto-assigned): {len(single_sense)}")
    print(f"Multi-sense (needs Hermes): {len(words_with_candidates)}")
    print(f"No WordNet match: {len(no_match)}")

    # Show single-sense assignments
    if single_sense:
        print("\n--- AUTO-ASSIGNED (single sense) ---")
        for s in single_sense:
            print(f'  "{s["word"]}" -> {s["assigned_ili"]} ({s["senses"][0]["pos"]}) "{s["senses"][0]["definition"][:60]}"')

    # Show no-match words
    if no_match:
        print("\n--- NO WORDNET MATCH ---")
        for nm in no_match:
            print(f'  "{nm["word"]}" — context: "{nm["context"][:60]}..."')

    # Send multi-sense words to Hermes
    if words_with_candidates:
        print(f"\n--- SENDING {len(words_with_candidates)} MULTI-SENSE WORDS TO HERMES ---")

        # Format the batch
        lines = []
        for i, wc in enumerate(words_with_candidates, 1):
            sense_list = "; ".join(
                f'{s["ili"]} ({s["pos"]}): {s["definition"][:80]}'
                for s in wc['senses'][:6]  # cap at 6 senses to avoid huge messages
            )
            lines.append(
                f'{i}. "{wc["word"]}" — context: "{wc["context"]}"\n'
                f'   Candidates: [{sense_list}]'
            )

        user_msg = (
            f"Disambiguate these {len(words_with_candidates)} words. For each, pick "
            f"the candidate ILI that best fits the context.\n\n"
            + "\n".join(lines)
        )

        print(f"\nCalling Hermes API...")
        try:
            response = call_hermes(SYSTEM_PROMPT, user_msg, timeout=45)
            print(f"\nHermes response:\n{response}")
        except Exception as e:
            print(f"\nHermes error: {e}")
            response = f"ERROR: {e}"

        # Save everything
        output = {
            "source_ili": source_ili,
            "record_idx": record_idx,
            "existing_ili_count": len(existing_ilis),
            "single_sense_auto": [{
                "word": s["word"],
                "ili": s["assigned_ili"],
                "definition": s["senses"][0]["definition"][:100],
            } for s in single_sense],
            "multi_sense_hermes": [{
                "word": wc["word"],
                "context": wc["context"],
                "candidates": wc["senses"],
            } for wc in words_with_candidates],
            "no_match": [nm["word"] for nm in no_match],
            "hermes_response": response,
        }
    else:
        output = {
            "source_ili": source_ili,
            "record_idx": record_idx,
            "existing_ili_count": len(existing_ilis),
            "single_sense_auto": [{
                "word": s["word"],
                "ili": s["assigned_ili"],
                "definition": s["senses"][0]["definition"][:100],
            } for s in single_sense],
            "multi_sense_hermes": [],
            "no_match": [nm["word"] for nm in no_match],
            "hermes_response": "N/A - no multi-sense words",
        }

    out_path = "/tmp/hermes_v2_record0.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results saved to {out_path}")

    db_conn.close()


if __name__ == "__main__":
    main()
