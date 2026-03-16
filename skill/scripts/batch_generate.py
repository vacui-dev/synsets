#!/usr/bin/env python3
"""
Batch Synset Generator — Two-Pass Advanced Model Edition

Pass 1: Generate natural definitions (no ILI awareness — pure encyclopedic knowledge)
Pass 2: Annotate definitions with ILI tags (post-processing — batched tool lookups)

The key insight: synset annotation should NEVER influence the content of definitions.
Definitions are written from knowledge. Annotations are applied from WordNet.
These are separate concerns, and separating them produces better data.

Usage:
    python batch_generate.py --count 10
    python batch_generate.py --start 1000 --count 20
    python batch_generate.py --ili 46360 --ili 59245
    python batch_generate.py --count 3 --dry-run
"""

import argparse
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_DIR / "data" / "synsets"
WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")

LANGUAGES = ["en", "zh", "ja"]
MAX_ILI_ID = 117480

STOPWORDS_EN = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each",
    "all", "both", "few", "many", "much", "several", "such",
    "i", "me", "we", "us", "you", "he", "him", "she", "it", "they", "them",
    "myself", "yourself", "himself", "herself", "itself", "ourselves", "themselves",
    "who", "whom", "whose", "which", "what", "whoever", "that",
    "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "along", "until", "upon", "toward", "towards",
    "across", "against", "among", "around", "behind", "beyond", "within",
    "without", "throughout", "despite", "over", "near", "beside",
    "and", "but", "or", "nor", "so", "yet", "for", "because", "although",
    "though", "while", "whereas", "if", "unless", "since", "whether",
    "either", "neither", "than",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "having", "do", "does", "did", "doing",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "must", "not", "very", "also", "just", "only", "even", "still",
    "already", "then", "too", "here", "there", "where", "when", "how",
    "why", "now", "never", "always", "often", "ever", "quite", "rather",
    "something", "anything", "everything", "nothing",
    "one", "two", "three", "etc", "non", "like", "well", "way",
})


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(WORDNET_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-64000")
    return conn


def get_synset_info(conn, ili_num: int) -> dict | None:
    """Get basic synset info for prompt context."""
    ili_id = f"i{ili_num}"
    row = conn.execute("""
        SELECT sy.pos, d.definition
        FROM ilis i
        JOIN synsets sy ON sy.ili_rowid = i.rowid
        JOIN definitions d ON d.synset_rowid = sy.rowid
        WHERE i.id = ? LIMIT 1
    """, (ili_id,)).fetchone()
    if not row:
        return None

    lemmas = [r["form"] for r in conn.execute("""
        SELECT DISTINCT f.form
        FROM synsets sy JOIN ilis i ON sy.ili_rowid = i.rowid
        JOIN senses s ON s.synset_rowid = sy.rowid
        JOIN entries e ON s.entry_rowid = e.rowid
        JOIN forms f ON f.entry_rowid = e.rowid
        WHERE i.id = ? ORDER BY s.entry_rank LIMIT 15
    """, (ili_id,)).fetchall()]

    return {"ili": ili_num, "pos": row["pos"], "definition": row["definition"], "lemmas": lemmas}


def simple_lemmatize(word: str) -> list[str]:
    """Candidate lemmas by suffix stripping."""
    candidates = [word]
    w = word.lower()
    if w.endswith("ing") and len(w) > 5:
        candidates.append(w[:-3])
        candidates.append(w[:-3] + "e")
        if len(w) > 6 and w[-4] == w[-5]:
            candidates.append(w[:-4])
    if w.endswith("ed") and len(w) > 4:
        candidates.append(w[:-2])
        candidates.append(w[:-1])
        if w.endswith("ied"):
            candidates.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 4:
        candidates.append(w[:-2])
        candidates.append(w[:-1])
    if w.endswith("ies") and len(w) > 5:
        candidates.append(w[:-3] + "y")
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        candidates.append(w[:-1])
    if w.endswith("ly") and len(w) > 4:
        candidates.append(w[:-2])
    if w.endswith("ness") and len(w) > 6:
        candidates.append(w[:-4])
    if w.endswith("ment") and len(w) > 6:
        candidates.append(w[:-4])
    return list(dict.fromkeys(candidates))


def lookup_word_batch(conn, words: list[str]) -> dict[str, list[dict]]:
    """Batch lookup many words at once. Returns {word: [senses]}."""
    results = {w: [] for w in words}
    seen = set()

    for word in words:
        candidates = simple_lemmatize(word)
        for candidate in candidates:
            rows = conn.execute("""
                SELECT DISTINCT i.id AS ili_id, e.pos, d.definition, f.form
                FROM forms f
                JOIN entries e ON f.entry_rowid = e.rowid
                JOIN senses s ON s.entry_rowid = e.rowid
                JOIN synsets sy ON s.synset_rowid = sy.rowid
                JOIN ilis i ON sy.ili_rowid = i.rowid
                JOIN definitions d ON d.synset_rowid = sy.rowid
                WHERE LOWER(f.form) = LOWER(?)
                ORDER BY s.entry_rank, s.synset_rank LIMIT 10
            """, (candidate,)).fetchall()

            if rows:
                for r in rows:
                    key = (word, r["ili_id"])
                    if key not in seen:
                        seen.add(key)
                        ili_num = int(r["ili_id"][1:])
                        results[word].append({
                            "ili": ili_num,
                            "ili_token": f"<|i{ili_num}|>",
                            "pos": r["pos"],
                            "definition": r["definition"],
                            "form": r["form"],
                        })
                break  # Use first candidate that matched

    return results


def extract_content_words(text: str) -> list[str]:
    """Extract unique content words from text, excluding stopwords."""
    words = re.findall(r"[a-zA-Z\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", text.lower())
    content = []
    seen = set()
    for w in words:
        if len(w) >= 2 and w not in STOPWORDS_EN and w not in seen and not w.isdigit():
            content.append(w)
            seen.add(w)
    return content


# ---------------------------------------------------------------------------
# Pass 1: Natural Definition Generation
# ---------------------------------------------------------------------------

def build_pass1_prompt(batch_info: list[dict], langs: list[str]) -> str:
    """Build prompt for natural definition generation (no ILI awareness)."""

    concept_blocks = []
    for s in batch_info:
        lemmas_str = ", ".join(s["lemmas"][:8])
        pos_label = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb", "s": "adjective"}.get(s["pos"], s["pos"])
        concept_blocks.append(
            f"  {s['ili']}. {lemmas_str} ({pos_label}): {s['definition']}"
        )

    concepts = "\n".join(concept_blocks)

    lang_instructions = {
        "en": """Write a natural English definition for each concept.
- 3-5 sentences of encyclopedic prose
- Cover: what it is, how it works, context, notable examples
- Write as if for Wikipedia — informative, neutral, precise
- Do NOT reference WordNet, ILI, or synsets in your writing""",

        "zh": """为每个概念撰写自然的中文定义。
- 3-5句百科全书式的文章
- 涵盖：是什么、如何运作、背景、典型例子
- 像维基百科一样写作——信息丰富、中立、精确
- 不要提及WordNet、ILI或同义词集""",

        "ja": """各概念の自然な日本語定義を書いてください。
- 3-5文の百科事典的な文章
- カバー：何か、どのように機能するか、背景、典型的な例
- ウィキペディアのように書いてください——有益で、中立で、正確
- WordNet、ILI、同義語セットに言及しないでください""",
    }

    lang_sections = []
    for l in langs:
        label = {"en": "English", "zh": "Chinese", "ja": "Japanese"}[l]
        lang_sections.append(f"### {label} ({l})\n{lang_instructions[l]}")

    lang_block = "\n\n".join(lang_sections)
    lang_list = ", ".join(langs)

    return f"""You are an encyclopedic writer. Write high-quality definitions for the following concepts in {lang_list}.

## Concepts

{concepts}

## Your Task

For EACH concept above, write definitions in all {len(langs)} languages.

{lang_block}

## Output Format

Return JSON:
```json
{{
  "definitions": [
    {{
      "ili": 12345,
      "natural": {{
        "en": "English definition text...",
        "zh": "中文定义文本...",
        "ja": "日本語の定義テキスト..."
      }}
    }}
  ]
}}
```

Write the definitions. No ILI tags, no WordNet references — just clean encyclopedic prose.
"""


# ---------------------------------------------------------------------------
# Pass 2: ILI Annotation (Post-Processing)
# ---------------------------------------------------------------------------

def build_pass2_prompt(definitions: dict[int, dict[str, str]], lookup_results: dict[int, dict[str, list[dict]]]) -> str:
    """Build prompt for ILI annotation pass.

    definitions: {ili_num: {lang: text}}
    lookup_results: {ili_num: {lang: {word: [senses]}}}
    """

    def_blocks = []
    for ili_num, lang_texts in sorted(definitions.items()):
        block_lines = [f"### ILI_{ili_num:06d}"]
        word_senses = lookup_results.get(ili_num, {})

        for lang, text in lang_texts.items():
            block_lines.append(f"\n**{lang}**: {text}")

        # Add WordNet sense table
        if word_senses:
            block_lines.append("\nWordNet senses:")
            for word, senses in sorted(word_senses.items()):
                sense_strs = []
                for s in senses[:5]:
                    sense_strs.append(f"ILI_{s['ili']:06d} ({s['pos']}): {s['definition'][:60]}")
                block_lines.append(f"  {word}: {'; '.join(sense_strs)}")

        def_blocks.append("\n".join(block_lines))

    all_defs = "\n\n---\n\n".join(def_blocks)

    return f"""You are a word sense disambiguation system. Your job is to annotate the following definitions with ILI (Interlingual Index) concept tags.

For each definition, tag EVERY CONTENT WORD with its correct ILI from the provided WordNet sense table.

## Definitions to Annotate

{all_defs}

## Annotation Rules

1. **Tag content words only**: nouns, verbs, adjectives, adverbs
2. **Do NOT tag function words**: determiners (the, a, an), prepositions (of, in, to, for, with, on, at, from, by), conjunctions (and, but, or), auxiliaries (is, am, are, was, were, has, have, had, do, does, did, will, would, may, might, can, could, should), pronouns (I, you, he, she, it, we, they)
3. **Chinese function words**: 的、了、在、和、或、与、是、把、被、就、也、都、还
4. **Japanese particles**: は、を、が、に、で、と、の、も、か、から、まで、より
5. **Disambiguate using context**: pick the sense that fits the sentence, not just the most common sense
6. **Format**: `<|ILI_NNNNNN|>word` where NNNNNN is zero-padded 6-digit ILI

## Output Format

Return JSON:
```json
{{
  "annotated": [
    {{
      "ili": 12345,
      "texts": {{
        "en": "<|ILI_12345|>word <|ILI_67890|>another...",
        "zh": "<|ILI_12345|>词 <||ILI_67890|>另一个...",
        "ja": "<|ILI_12345|>単語 <|ILI_67890|>別の..."
      }},
      "ili_counts": {{"en": 15, "zh": 15, "ja": 15}}
    }}
  ]
}}
```

Annotate all definitions. Use the WordNet sense tables provided.
"""


# ---------------------------------------------------------------------------
# Model Invocation
# ---------------------------------------------------------------------------

def get_model_info() -> str:
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                if "default:" in line:
                    return line.split(":", 1)[1].strip()
    return "openrouter/hunter-alpha"


def invoke_model(prompt: str, model: str, timeout: int = 600, dry_run: bool = False) -> str | None:
    if dry_run:
        print("=" * 80)
        print(f"DRY RUN — {len(prompt)} char prompt:")
        print("=" * 80)
        print(prompt[:2000])
        if len(prompt) > 2000:
            print(f"\n... ({len(prompt)} total chars)")
        return None

    print(f"  Invoking {model} ({len(prompt)} chars)...", file=sys.stderr)
    t0 = time.time()

    result = subprocess.run(
        ["hermes", "chat", "--yolo", "--query", prompt],
        capture_output=True, text=True, timeout=timeout,
    )

    elapsed = time.time() - t0
    print(f"  Response: {elapsed:.1f}s, {len(result.stdout)} chars", file=sys.stderr)

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:500]}", file=sys.stderr)
        return None

    return result.stdout


def extract_json(output: str) -> dict | None:
    """Extract JSON from model output."""
    patterns = [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
        r'(\{[^{}]*"definitions"\s*:\s*\[.*?\]\s*\})',
        r'(\{[^{}]*"annotated"\s*:\s*\[.*?\]\s*\})',
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(output.strip())
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# File Output
# ---------------------------------------------------------------------------

def write_synset(ili_num: int, natural: dict, annotated: dict, ili_counts: dict, model: str):
    """Write synset data to directory structure."""
    base = DATA_DIR / f"ili_{ili_num:06d}" / model
    for subdir in ["natural", "ili", "merged"]:
        (base / subdir).mkdir(parents=True, exist_ok=True)

    for lang in LANGUAGES:
        if lang in natural:
            (base / "natural" / f"{lang}.txt").write_text(natural[lang], encoding="utf-8")
        if lang in annotated:
            (base / "ili" / f"{lang}.txt").write_text(annotated[lang], encoding="utf-8")
            (base / "merged" / f"{lang}.txt").write_text(annotated[lang], encoding="utf-8")

    meta = {
        "ili": ili_num,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "languages": LANGUAGES,
        "generation_method": "batch_two_pass",
        "ilis_per_lang": ili_counts,
        "alignment_verified": len(set(ili_counts.values())) <= 1 if ili_counts else False,
    }
    meta_path = DATA_DIR / f"ili_{ili_num:06d}" / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# ILI Selection
# ---------------------------------------------------------------------------

def get_existing_ilis() -> set[int]:
    existing = set()
    if DATA_DIR.exists():
        for d in DATA_DIR.iterdir():
            if d.name.startswith("ili_"):
                try:
                    existing.add(int(d.name.split("_")[1]))
                except (ValueError, IndexError):
                    pass
    return existing


def select_ilis(count: int, start: int | None = None) -> list[int]:
    existing = get_existing_ilis()
    if start is not None:
        return [i for i in range(start, start + count * 3) if i not in existing][:count]
    selected = []
    while len(selected) < count:
        ili = random.randint(1, MAX_ILI_ID)
        if ili not in existing and ili not in selected:
            selected.append(ili)
    return selected


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch ILI synset generator — two-pass edition")
    parser.add_argument("--count", type=int, default=5, help="Number of ILIs")
    parser.add_argument("--start", type=int, help="Start ILI (range mode)")
    parser.add_argument("--ili", type=int, action="append", dest="ilis", help="Specific ILI")
    parser.add_argument("--langs", default=",".join(LANGUAGES))
    parser.add_argument("--model", help="Model override")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    args = parser.parse_args()

    model = args.model or get_model_info()
    langs = args.langs.split(",")

    # Select ILIs
    ili_nums = args.ilis if args.ilis else select_ilis(args.count, args.start)
    if not ili_nums:
        print("No ILIs to process"); return

    print(f"Batch: {len(ili_nums)} ILIs | Model: {model} | Langs: {langs}")
    print(f"ILIs: {ili_nums}")

    # Research from WordNet
    conn = get_db()
    batch_info = []
    for n in ili_nums:
        info = get_synset_info(conn, n)
        if info:
            batch_info.append(info)
    conn.close()

    if not batch_info:
        print("ERROR: No valid synsets"); return
    print(f"Found {len(batch_info)} valid synsets in WordNet")

    # ===== PASS 1: Natural Definitions =====
    print(f"\n{'='*60}")
    print("PASS 1: Generating natural definitions (no ILI awareness)")
    print(f"{'='*60}")

    pass1_prompt = build_pass1_prompt(batch_info, langs)
    pass1_output = invoke_model(pass1_prompt, model, timeout=600, dry_run=args.dry_run)

    if args.dry_run or pass1_output is None:
        return

    pass1_data = extract_json(pass1_output)
    if not pass1_data or "definitions" not in pass1_data:
        print("ERROR: Failed to parse Pass 1 output")
        debug = PROJECT_DIR / "output" / f"pass1_debug_{int(time.time())}.txt"
        debug.parent.mkdir(exist_ok=True)
        debug.write_text(pass1_output, encoding="utf-8")
        print(f"Saved to {debug}")
        return

    # Extract definitions
    definitions = {}  # {ili_num: {lang: text}}
    for entry in pass1_data["definitions"]:
        ili_num = entry.get("ili")
        if ili_num and "natural" in entry:
            definitions[ili_num] = entry["natural"]

    print(f"Pass 1 generated {len(definitions)} definitions")

    # ===== PASS 2: ILI Annotation =====
    print(f"\n{'='*60}")
    print("PASS 2: Annotating with ILI tags (batched WordNet lookups)")
    print(f"{'='*60}")

    # Batch lookup all content words for all definitions
    print("Looking up content words in WordNet...")
    conn = get_db()
    lookup_results = {}  # {ili_num: {lang: {word: [senses]}}}
    total_words = 0

    for ili_num, lang_texts in definitions.items():
        lookup_results[ili_num] = {}
        for lang, text in lang_texts.items():
            content_words = extract_content_words(text)
            if content_words:
                senses = lookup_word_batch(conn, content_words)
                lookup_results[ili_num][lang] = senses
                total_words += len(content_words)

    conn.close()
    print(f"  Looked up {total_words} content words across {len(definitions)} synsets")

    # Build and send Pass 2 prompt
    pass2_prompt = build_pass2_prompt(definitions, lookup_results)
    pass2_output = invoke_model(pass2_prompt, model, timeout=900, dry_run=args.dry_run)

    if args.dry_run or pass2_output is None:
        # Still save natural definitions without annotation
        print("Saving natural definitions only (no annotation)...")
        for ili_num, lang_texts in definitions.items():
            base = DATA_DIR / f"ili_{ili_num:06d}" / model
            for subdir in ["natural", "ili", "merged"]:
                (base / subdir).mkdir(parents=True, exist_ok=True)
            for lang, text in lang_texts.items():
                (base / "natural" / f"{lang}.txt").write_text(text, encoding="utf-8")
        return

    pass2_data = extract_json(pass2_output)
    if not pass2_data or "annotated" not in pass2_data:
        print("WARNING: Failed to parse Pass 2 output, saving natural only")
        pass2_data = {"annotated": []}

    # Merge pass1 (natural) + pass2 (annotated) and write
    annotated_map = {}  # {ili_num: {lang: annotated_text}}
    counts_map = {}     # {ili_num: {lang: count}}
    for entry in pass2_data["annotated"]:
        ili_num = entry.get("ili")
        if ili_num:
            annotated_map[ili_num] = entry.get("texts", {})
            counts_map[ili_num] = entry.get("ili_counts", {})

    written = []
    for ili_num in definitions:
        natural = definitions[ili_num]
        annotated = annotated_map.get(ili_num, {})
        counts = counts_map.get(ili_num, {})
        write_synset(ili_num, natural, annotated, counts, model)
        written.append(ili_num)
        total_ilis = sum(counts.values()) if counts else 0
        print(f"  ili_{ili_num:06d}: {total_ilis} ILI tags across {len(annotated)} langs")

    print(f"\nWrote {len(written)} synsets")

    # Commit
    if not args.no_commit and written:
        msg = f"Batch synset generation: {len(written)} ILIs [{model}] two-pass"
        subprocess.run(["git", "-C", str(PROJECT_DIR), "add", "data/synsets/"], check=False)
        r = subprocess.run(["git", "-C", str(PROJECT_DIR), "commit", "-m", msg], capture_output=True, text=True)
        if r.returncode == 0:
            print(f"Committed: {msg}")
        else:
            print("No changes to commit")


if __name__ == "__main__":
    main()
