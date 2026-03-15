#!/usr/bin/env python3
"""
Hermes Tool Use — Give Hermes direct access to WordNet via function calling.

Loads a corpus record, extracts content words from plaintext gaps between
ILI tokens, and lets Hermes look up WordNet senses via tool calls to
disambiguate and assign ILI IDs.

Usage:
    python skill/scripts/hermes_tool_use.py [--record N]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")
CORPUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "synset_corpus_v4_converted_full.jsonl",
)
ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)
API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
MODEL = "Hermes-4-405B"
TIMEOUT = 180
TEMPERATURE = 0.3
MAX_TOKENS = 8192

# ILI token pattern: <|iNNNNN|> or <|ILI_NNNNNN|>
ILI_TOKEN_RE = re.compile(r"<\|(?:i(\d+)|ILI_(\d+))\|>")

# ---------------------------------------------------------------------------
# Stopwords — hardcoded, no external NLP
# ---------------------------------------------------------------------------

STOPWORDS = frozenset({
    # determiners
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each",
    "all", "both", "few", "many", "much", "several", "such",
    # pronouns
    "i", "me", "we", "us", "you", "he", "him", "she", "it", "they", "them",
    "myself", "yourself", "himself", "herself", "itself", "ourselves",
    "themselves", "who", "whom", "whose", "which", "what", "whoever",
    # prepositions
    "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "along", "until", "upon", "toward", "towards",
    "across", "against", "among", "around", "behind", "beyond", "within",
    "without", "throughout", "despite", "over", "near", "beside", "besides",
    # conjunctions
    "and", "but", "or", "nor", "so", "yet", "for", "because", "although",
    "though", "while", "whereas", "if", "unless", "since", "whether",
    "either", "neither", "than",
    # auxiliary / modal verbs
    "is", "am", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "must", "need", "dare", "ought",
    # adverbs (function-word-like)
    "not", "very", "also", "just", "only", "even", "still", "already",
    "then", "too", "here", "there", "where", "when", "how", "why",
    "now", "never", "always", "often", "ever", "quite", "rather",
    # indefinite pronouns
    "something", "anything", "everything", "nothing",
    "someone", "anyone", "everyone", "nobody", "somebody", "anybody",
    "somewhere", "anywhere", "everywhere", "nowhere",
    # other function words
    "s", "t", "d", "ll", "re", "ve", "m",  # contractions
    "etc", "e", "g", "ie", "vs",
    # misc
    "non", "like", "well", "way", "part", "one", "two", "three",
})

# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------


def load_api_key() -> str:
    if os.environ.get("NOUS_API_KEY"):
        return os.environ["NOUS_API_KEY"]
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("NOUS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key. Set NOUS_API_KEY env var or put it in .env")
    sys.exit(1)


# ---------------------------------------------------------------------------
# WordNet DB tools
# ---------------------------------------------------------------------------


_DB_CONN = None

def get_db():
    """Return a persistent sqlite3 connection to the WordNet DB."""
    global _DB_CONN
    if _DB_CONN is None:
        if not os.path.exists(WORDNET_DB):
            print(f"ERROR: WordNet DB not found at {WORDNET_DB}")
            sys.exit(1)
        _DB_CONN = sqlite3.connect(WORDNET_DB)
        _DB_CONN.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent read performance
        _DB_CONN.execute("PRAGMA journal_mode=WAL")
        _DB_CONN.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return _DB_CONN


def simple_lemmatize(word: str) -> list[str]:
    """Generate candidate lemmas by stripping common English suffixes."""
    candidates = [word]
    w = word.lower()
    # Verb inflections
    if w.endswith("ing") and len(w) > 5:
        candidates.append(w[:-3])        # running -> runn (won't match, harmless)
        candidates.append(w[:-3] + "e")  # emerging -> emerge
        if len(w) > 6 and w[-4] == w[-5]:
            candidates.append(w[:-4])    # running -> run
    if w.endswith("ed") and len(w) > 4:
        candidates.append(w[:-2])        # constrained -> constrain
        candidates.append(w[:-1])        # emerged -> emerge (via -d)
        if w.endswith("ied"):
            candidates.append(w[:-3] + "y")  # carried -> carry
    if w.endswith("es") and len(w) > 4:
        candidates.append(w[:-2])        # goes -> go
        candidates.append(w[:-1])        # makes -> make (via -s)
    if w.endswith("ies") and len(w) > 5:
        candidates.append(w[:-3] + "y")  # boundaries -> boundary
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        candidates.append(w[:-1])        # represents -> represent
    # Adjective/adverb
    if w.endswith("ly") and len(w) > 4:
        candidates.append(w[:-2])        # quickly -> quick
    if w.endswith("ness") and len(w) > 6:
        candidates.append(w[:-4])        # darkness -> dark
    if w.endswith("ment") and len(w) > 6:
        candidates.append(w[:-4])        # establishment -> establish
    return list(dict.fromkeys(candidates))  # dedupe, preserve order


def tool_lookup_word(word: str, pos: str | None = None) -> list[dict]:
    """Look up all senses of a word in WordNet, return ILI IDs + definitions."""
    conn = get_db()

    # Try the word as-is, then lemmatized forms
    candidates = simple_lemmatize(word)

    all_rows = []
    for candidate in candidates:
        query = """
            SELECT DISTINCT
                i.id   AS ili_id,
                e.pos  AS pos,
                d.definition AS definition,
                f.form AS form
            FROM forms f
            JOIN entries e   ON f.entry_rowid = e.rowid
            JOIN senses s    ON s.entry_rowid  = e.rowid
            JOIN synsets sy  ON s.synset_rowid  = sy.rowid
            JOIN ilis i      ON sy.ili_rowid    = i.rowid
            JOIN definitions d ON d.synset_rowid = sy.rowid
            WHERE LOWER(f.form) = LOWER(?)
        """
        params = [candidate]
        if pos:
            query += " AND e.pos = ?"
            params.append(pos)
        query += " ORDER BY s.entry_rank, s.synset_rank LIMIT 30"

        rows = conn.execute(query, params).fetchall()
        if rows:
            all_rows = rows
            break  # Use first candidate that matches


    rows = all_rows

    results = []
    for r in rows:
        ili_num = int(r["ili_id"][1:])  # strip leading 'i'
        results.append({
            "ili_id": r["ili_id"],
            "ili_num": ili_num,
            "ili_token": f"<|i{ili_num}|>",
            "pos": r["pos"],
            "definition": r["definition"],
            "form": r["form"],
        })
    return results


def tool_lookup_phrase(phrase: str) -> list[dict]:
    """Check if a multi-word phrase exists as a WordNet entry."""
    conn = get_db()
    # WordNet stores multi-word entries with spaces
    query = """
        SELECT DISTINCT
            i.id   AS ili_id,
            e.pos  AS pos,
            d.definition AS definition,
            f.form AS form
        FROM forms f
        JOIN entries e   ON f.entry_rowid = e.rowid
        JOIN senses s    ON s.entry_rowid  = e.rowid
        JOIN synsets sy  ON s.synset_rowid  = sy.rowid
        JOIN ilis i      ON sy.ili_rowid    = i.rowid
        JOIN definitions d ON d.synset_rowid = sy.rowid
        WHERE LOWER(f.form) = LOWER(?)
        ORDER BY s.entry_rank, s.synset_rank
        LIMIT 20
    """
    rows = conn.execute(query, [phrase]).fetchall()


    results = []
    for r in rows:
        ili_num = int(r["ili_id"][1:])
        results.append({
            "ili_id": r["ili_id"],
            "ili_num": ili_num,
            "ili_token": f"<|i{ili_num}|>",
            "pos": r["pos"],
            "definition": r["definition"],
            "form": r["form"],
        })
    return results


def tool_search_definition(query_text: str) -> list[dict]:
    """Search definitions for concepts matching a description."""
    conn = get_db()
    # Use LIKE with wildcards around each significant word
    words = [w.strip() for w in query_text.lower().split() if len(w.strip()) > 2]
    if not words:
    
        return []

    # Build query: all words must appear in definition
    where_clauses = []
    params = []
    for w in words[:5]:  # limit to 5 keywords
        where_clauses.append("LOWER(d.definition) LIKE ?")
        params.append(f"%{w}%")

    query = f"""
        SELECT DISTINCT
            i.id AS ili_id,
            d.definition AS definition,
            sy.pos AS pos
        FROM definitions d
        JOIN synsets sy ON d.synset_rowid = sy.rowid
        JOIN ilis i    ON sy.ili_rowid = i.rowid
        WHERE {' AND '.join(where_clauses)}
        LIMIT 10
    """
    rows = conn.execute(query, params).fetchall()


    results = []
    for r in rows:
        ili_num = int(r["ili_id"][1:])
        results.append({
            "ili_id": r["ili_id"],
            "ili_num": ili_num,
            "ili_token": f"<|i{ili_num}|>",
            "pos": r["pos"],
            "definition": r["definition"],
        })
    return results


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "lookup_word": tool_lookup_word,
    "lookup_phrase": tool_lookup_phrase,
    "search_definition": tool_search_definition,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_word",
            "description": (
                "Look up all senses of a word in WordNet. Returns ILI IDs, "
                "part of speech, and definitions for each sense. Use this to "
                "find the correct ILI ID for a word in context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "The word to look up (single word, lowercase)",
                    },
                    "pos": {
                        "type": "string",
                        "enum": ["n", "v", "a", "r"],
                        "description": (
                            "Optional part-of-speech filter: "
                            "n=noun, v=verb, a=adjective, r=adverb"
                        ),
                    },
                },
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_phrase",
            "description": (
                "Check if a multi-word phrase exists as a WordNet entry. "
                "Use for compound terms like 'ice cream', 'hot dog', "
                "'take off', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "The multi-word phrase to look up",
                    },
                },
                "required": ["phrase"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_definition",
            "description": (
                "Search WordNet definitions for concepts matching a "
                "description. Use when you know what a concept means but "
                "don't know the exact word, or when you want to find ILI IDs "
                "for abstract concepts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Description of the concept to search for. "
                            "Use key content words."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Corpus loading & text processing
# ---------------------------------------------------------------------------


def load_record(n: int) -> dict:
    """Load the Nth record from the corpus JSONL."""
    with open(CORPUS) as f:
        for i, line in enumerate(f):
            if i == n:
                return json.loads(line)
    print(f"ERROR: Record {n} not found in corpus")
    sys.exit(1)


def extract_gaps_and_words(text: str) -> list[dict]:
    """
    Find plaintext gaps between ILI tokens, tokenize into words,
    filter out stopwords. Returns list of {word, position, context}.
    """
    # Split text by ILI tokens, keeping track of positions
    parts = ILI_TOKEN_RE.split(text)
    # parts alternates: text, group1, group2, text, group1, group2, ...
    # Each match produces 2 groups (one is None depending on format)

    content_words = []
    word_id = 0

    # Walk through the split parts, collecting plaintext segments
    idx = 0
    while idx < len(parts):
        segment = parts[idx]
        if segment is None:
            idx += 1
            continue

        # Check if this is an ILI group match (numeric string from capture)
        if segment.isdigit() and len(segment) <= 6:
            idx += 1
            continue

        # This is a plaintext segment — tokenize it
        # Remove markdown formatting
        clean = re.sub(r"[#*\[\](){}|<>:;,.\-!?\"'/\\=+_~`@^&]", " ", segment)
        tokens = clean.lower().split()

        for tok in tokens:
            tok = tok.strip()
            if not tok or len(tok) < 2:
                continue
            if tok in STOPWORDS:
                continue
            if tok.isdigit():
                continue
            # Build a short context window from the segment
            context_snippet = segment.strip()[:120]
            content_words.append({
                "word": tok,
                "id": word_id,
                "context": context_snippet,
            })
            word_id += 1

        idx += 1

    # Deduplicate: keep unique words but track all positions
    seen = {}
    deduped = []
    for w in content_words:
        key = w["word"]
        if key not in seen:
            seen[key] = w
            deduped.append(w)

    return deduped


def count_ili_tokens(text: str) -> int:
    """Count how many ILI tokens are in the text."""
    return len(ILI_TOKEN_RE.findall(text))


# ---------------------------------------------------------------------------
# API calling
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a word sense disambiguation agent with access to WordNet lookup tools.

CRITICAL RULES:
- You MUST call lookup_word for EVERY content word before making any assignments.
- You MUST NOT guess or invent ILI IDs. EVERY ILI ID in your output must come
  from a tool call result.
- You WILL hallucinate ILI IDs if you try to produce them from memory. You have
  been tested on this and you failed. USE THE TOOLS.
- Call lookup_word with each word. You can batch multiple calls per turn.
- After ALL lookups are done, return your final JSON assignments.

WORKFLOW:
1. Call lookup_word for each content word (you can do several per turn)
2. Read the results — each result shows all WordNet senses with ILI IDs
3. Pick the correct sense based on the document context (word sense disambiguation)
4. After ALL words are looked up, return this JSON:

```json
{
  "assignments": [
    {"word": "example", "ili_num": 12345, "ili_token": "<|i12345|>", "definition": "the definition", "confidence": "high"},
    ...
  ]
}
```

If two adjacent words form a compound (e.g., "ice cream"), use lookup_phrase.
If you know a meaning but not the word, use search_definition.

START by calling lookup_word for the first batch of content words. Do NOT
produce any ILI numbers until you have tool results."""


def call_hermes(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """
    Call Hermes API. Returns the raw message dict from the response,
    which may contain 'content' and/or 'tool_calls'.
    """
    api_key = load_api_key()

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "reasoning": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    data = json.dumps(payload).encode()

    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        result = json.loads(resp.read())

    choice = result["choices"][0]
    return choice["message"]


def execute_tool_call(tool_call: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    func_name = tool_call["function"]["name"]
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid JSON arguments: {tool_call['function']['arguments']}"})

    func = TOOL_FUNCTIONS.get(func_name)
    if not func:
        return json.dumps({"error": f"Unknown function: {func_name}"})

    try:
        result = func(**args)
        if not result:
            return json.dumps({
                "result": [],
                "note": f"No WordNet entry found for '{args.get('word', args.get('phrase', args.get('query', '')))}'. "
                        "This word may not be in WordNet. Skip it and move on to your final assignments."
            })
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run(record_num: int, word_limit: int = 20):
    # 1. Load record
    print(f"Loading record {record_num}...")
    record = load_record(record_num)
    text = record["text"]
    existing_count = count_ili_tokens(text)

    print(f"\n{'='*70}")
    print("ORIGINAL TEXT (first 500 chars):")
    print(f"{'='*70}")
    print(text[:500])
    if len(text) > 500:
        print(f"... ({len(text)} total chars)")
    print(f"\nExisting ILI tokens: {existing_count}")

    # 2. Extract content words
    all_content_words = extract_gaps_and_words(text)
    content_words = all_content_words[:word_limit]
    print(f"\n{'='*70}")
    print(f"CONTENT WORDS EXTRACTED: {len(all_content_words)} (sending {len(content_words)})")
    print(f"{'='*70}")
    for w in content_words:
        print(f"  [{w['id']:3d}] {w['word']}")
    if len(all_content_words) > word_limit:
        print(f"  ... ({len(all_content_words) - word_limit} more not sent)")

    if not content_words:
        print("\nNo content words found in gaps. Nothing to annotate.")
        return

    # 3. Build the initial message to Hermes
    word_list = "\n".join(
        f"  {w['id']}. \"{w['word']}\" — context: \"{w['context'][:80]}\""
        for w in content_words
    )

    user_msg = f"""Here is a document with ILI (Interlingual Index) annotations. Some words
in the plaintext gaps between ILI tokens are not yet annotated. Please look up
each content word using the tools and assign the correct ILI ID based on context.

DOCUMENT TEXT:
{text}

CONTENT WORDS TO ANNOTATE:
{word_list}

Please look up each word and select the correct WordNet sense based on the
document context. Start with lookup_word for each word."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # 4. Tool-use loop
    iteration = 0
    max_iterations = 10  # safety limit

    print(f"\n{'='*70}")
    print("HERMES TOOL-USE LOOP")
    print(f"{'='*70}")

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        try:
            response = call_hermes(messages, tools=TOOL_DEFINITIONS)
        except Exception as e:
            print(f"API ERROR: {e}")
            break

        # Check if Hermes returned tool calls
        tool_calls = response.get("tool_calls")
        content = response.get("content")

        if content:
            print(f"Hermes says: {content[:200]}{'...' if len(content or '') > 200 else ''}")

        if not tool_calls:
            # Final response — no more tool calls
            if content:
                messages.append({"role": "assistant", "content": content})
            print("\nHermes finished (no more tool calls).")
            break

        # Execute each tool call
        print(f"Hermes made {len(tool_calls)} tool call(s):")

        # Add assistant message with tool calls to history
        messages.append(response)

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = tc["function"]["arguments"]
            tc_id = tc.get("id", "unknown")

            print(f"  -> {func_name}({json.dumps(func_args)})")

            result_str = execute_tool_call(tc)

            # Show abbreviated result
            result_preview = result_str[:200]
            if len(result_str) > 200:
                result_preview += "..."
            print(f"     Result: {result_preview}")

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_str,
            })

    # 5. Extract final assignments from Hermes's last content response
    final_content = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_content = msg["content"]
            break

    if not final_content:
        final_content = None

    print(f"\n{'='*70}")
    print("HERMES FINAL RESPONSE:")
    print(f"{'='*70}")
    if final_content:
        print(final_content)
    else:
        print("(no final content response)")
        return

    # 6. Try to parse assignments from the response
    assignments = []
    # Try multiple JSON extraction patterns
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", final_content, re.DOTALL)
    if not json_match:
        # Hermes sometimes wraps in <tool_call> tags
        json_match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", final_content, re.DOTALL)
    if not json_match:
        # Try bare JSON object
        json_match = re.search(r'(\{"assignments"\s*:\s*\[.*?\]\s*\})', final_content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            assignments = parsed.get("assignments", [])
        except json.JSONDecodeError:
            print("WARNING: Could not parse Hermes's JSON output")

    # 7. Show retranslated text and coverage
    print(f"\n{'='*70}")
    print("ASSIGNMENTS:")
    print(f"{'='*70}")

    new_tokens = {}
    for a in assignments:
        word = a.get("word", "")
        ili_num = a.get("ili_num")
        confidence = a.get("confidence", "?")
        definition = a.get("definition", "")[:60]
        if word and ili_num:
            new_tokens[word.lower()] = ili_num
            print(f"  {word:20s} -> <|i{ili_num}|>  [{confidence}]  {definition}")

    # 8. Build retranslated text — insert ILI tokens after matched words
    retranslated = text
    for word, ili_num in sorted(new_tokens.items(), key=lambda x: -len(x[0])):
        # Insert ILI token after the word (case-insensitive, whole word)
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        retranslated = pattern.sub(rf'\1 <|i{ili_num}|>', retranslated, count=1)

    new_count = count_ili_tokens(retranslated)

    print(f"\n{'='*70}")
    print("RETRANSLATED TEXT (first 500 chars):")
    print(f"{'='*70}")
    print(retranslated[:500])
    if len(retranslated) > 500:
        print(f"... ({len(retranslated)} total chars)")

    print(f"\n{'='*70}")
    print("COVERAGE STATS:")
    print(f"{'='*70}")
    print(f"  ILI tokens before:  {existing_count}")
    print(f"  ILI tokens after:   {new_count}")
    print(f"  New tokens added:   {new_count - existing_count}")
    print(f"  Content words sent: {len(content_words)}")
    print(f"  Assignments made:   {len(assignments)}")
    print(f"  Tool-use rounds:    {iteration}")


# ---------------------------------------------------------------------------
# Batch-capable record processor (returns structured data)
# ---------------------------------------------------------------------------


def process_record(record_num: int, word_limit: int = 100, verbose: bool = True) -> dict | None:
    """Process one record and return structured result dict, or None on failure."""
    try:
        record = load_record(record_num)
    except SystemExit:
        return None

    text = record["text"]
    existing_count = count_ili_tokens(text)

    all_content_words = extract_gaps_and_words(text)
    content_words = all_content_words[:word_limit]

    if not content_words:
        if verbose:
            print(f"  Record {record_num}: no content words, skipping", file=sys.stderr)
        return {
            "record_num": record_num,
            "source_ili": record.get("source_ili", ""),
            "original_text": text,
            "retranslated_text": text,
            "coverage_before": existing_count,
            "coverage_after": existing_count,
            "assignments": [],
            "skipped_words": [],
        }

    # Build message
    word_list = "\n".join(
        f"  {w['id']}. \"{w['word']}\" — context: \"{w['context'][:80]}\""
        for w in content_words
    )
    user_msg = f"""Here is a document with ILI annotations. Annotate the remaining content words.

DOCUMENT TEXT:
{text}

CONTENT WORDS TO ANNOTATE:
{word_list}

Look up each word and select the correct WordNet sense based on context. Start with lookup_word for each word."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Tool-use loop
    iteration = 0
    max_iterations = 10

    while iteration < max_iterations:
        iteration += 1
        try:
            response = call_hermes(messages, tools=TOOL_DEFINITIONS)
        except Exception as e:
            if verbose:
                print(f"  Record {record_num}: API error iter {iteration}: {e}", file=sys.stderr)
            if iteration == 1:
                # Retry once
                try:
                    response = call_hermes(messages, tools=TOOL_DEFINITIONS)
                except Exception:
                    return None
            else:
                break

        tool_calls = response.get("tool_calls")
        content = response.get("content")

        if not tool_calls:
            if content:
                messages.append({"role": "assistant", "content": content})
            break

        messages.append(response)
        for tc in tool_calls:
            result_str = execute_tool_call(tc)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", "unknown"),
                "content": result_str,
            })

    # Extract final content
    final_content = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_content = msg["content"]
            break

    if not final_content:
        if verbose:
            print(f"  Record {record_num}: no final response", file=sys.stderr)
        return None

    # Parse assignments
    assignments = []
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", final_content, re.DOTALL)
    if not json_match:
        json_match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", final_content, re.DOTALL)
    if not json_match:
        json_match = re.search(r'(\{"assignments"\s*:\s*\[.*?\]\s*\})', final_content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            assignments = parsed.get("assignments", [])
        except json.JSONDecodeError:
            if verbose:
                print(f"  Record {record_num}: JSON parse error", file=sys.stderr)

    # Build retranslated text
    new_tokens = {}
    skipped = []
    for a in assignments:
        word = a.get("word", "")
        ili_num = a.get("ili_num")
        if word and ili_num:
            new_tokens[word.lower()] = ili_num

    # Find skipped words
    assigned_words = {a.get("word", "").lower() for a in assignments if a.get("ili_num")}
    for w in content_words:
        if w["word"] not in assigned_words:
            skipped.append(w["word"])

    retranslated = text
    for word, ili_num in sorted(new_tokens.items(), key=lambda x: -len(x[0])):
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        retranslated = pattern.sub(rf'\1 <|i{ili_num}|>', retranslated, count=1)

    new_count = count_ili_tokens(retranslated)

    result = {
        "record_num": record_num,
        "source_ili": record.get("source_ili", ""),
        "original_text": text,
        "retranslated_text": retranslated,
        "coverage_before": existing_count,
        "coverage_after": new_count,
        "assignments": [
            {"word": a["word"], "ili": a["ili_num"], "pos": a.get("pos", ""),
             "definition": a.get("definition", "")[:100]}
            for a in assignments if a.get("ili_num")
        ],
        "skipped_words": skipped,
    }

    if verbose:
        print(f"  Record {record_num}: {existing_count} -> {new_count} tokens "
              f"({len(assignments)} assigned, {len(skipped)} skipped), "
              f"{iteration} rounds", file=sys.stderr)

    return result


def batch_process(start: int, count: int, output_path: str, word_limit: int = 100):
    """Process a range of records and save results to JSONL."""
    import time

    total = 0
    success = 0
    failed = 0
    total_before = 0
    total_after = 0

    print(f"Batch processing records {start}-{start+count-1} -> {output_path}", file=sys.stderr)
    print(f"Word limit per record: {word_limit}", file=sys.stderr)

    with open(output_path, "a") as out:
        for i in range(start, start + count):
            total += 1
            t0 = time.time()

            result = process_record(i, word_limit=word_limit, verbose=True)

            elapsed = time.time() - t0

            if result is None:
                failed += 1
                print(f"  FAILED record {i} ({elapsed:.1f}s)", file=sys.stderr)
                continue

            success += 1
            total_before += result["coverage_before"]
            total_after += result["coverage_after"]

            out.write(json.dumps(result) + "\n")
            out.flush()

            if total % 10 == 0:
                print(f"\n  === Progress: {total}/{count} records, "
                      f"{success} ok, {failed} failed, "
                      f"coverage {total_before} -> {total_after} "
                      f"(+{total_after - total_before}) ===\n", file=sys.stderr)

    print(f"\nDone: {success}/{total} records processed, {failed} failed.", file=sys.stderr)
    print(f"Coverage: {total_before} -> {total_after} (+{total_after - total_before})", file=sys.stderr)
    print(f"Output: {output_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Give Hermes direct WordNet tool access for ILI annotation"
    )
    parser.add_argument(
        "--record", type=int, default=None,
        help="Single record number to process"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max content words per record (default: 100)"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Batch processing mode"
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start record for batch mode (default: 0)"
    )
    parser.add_argument(
        "--count", type=int, default=20,
        help="Number of records for batch mode (default: 20)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSONL path for batch mode"
    )
    args = parser.parse_args()

    if args.batch:
        output = args.output or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "retranslated_v1.jsonl"
        )
        batch_process(args.start, args.count, output, word_limit=args.limit)
    elif args.record is not None:
        run(args.record, word_limit=args.limit)
    else:
        run(0, word_limit=args.limit)
