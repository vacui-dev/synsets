#!/usr/bin/env python3
"""
Common utilities shared across all synsets scripts.

Eliminates code duplication for:
- ILI token regex patterns
- Stopword lists
- Simple lemmatization
- API key loading
- Database access
- ILI token format conversion
"""

import os
import re
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")
WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")

# ---------------------------------------------------------------------------
# ILI Token Patterns
# ---------------------------------------------------------------------------

# Matches both formats: <|iNNNNN|> and <|ILI_NNNNNN|>
ILI_TOKEN_RE = re.compile(r"<\|(?:i|ILI_)(\d+)\|>")

# Matches only the canonical format: <|ILI_NNNNNN|>
ILI_CANONICAL_RE = re.compile(r"<\|ILI_(\d+)\|>")

# Matches only the internal format: <|iNNNNN|>
ILI_INTERNAL_RE = re.compile(r"<\|i(\d+)\|>")


def normalize_ili_token(ili_num: int) -> str:
    """Convert an ILI number to canonical <|ILI_NNNNNN|> format (zero-padded 6 digits)."""
    return f"<|ILI_{ili_num:06d}|>"


def internal_ili_token(ili_num: int) -> str:
    """Convert an ILI number to internal <|iNNNNN|> format (no padding)."""
    return f"<|i{ili_num}|>"


def ili_token_to_num(token: str) -> int | None:
    """Extract the ILI number from any supported token format."""
    m = ILI_TOKEN_RE.search(token)
    return int(m.group(1)) if m else None


def normalize_ili_text(text: str) -> str:
    """Convert all ILI tokens in text to canonical <|ILI_NNNNNN|> format."""
    def repl(m):
        return normalize_ili_token(int(m.group(1)))
    return ILI_TOKEN_RE.sub(repl, text)


def internal_ili_text(text: str) -> str:
    """Convert all ILI tokens in text to internal <|iNNNNN|> format."""
    def repl(m):
        return internal_ili_token(int(m.group(1)))
    return ILI_TOKEN_RE.sub(repl, text)


# ---------------------------------------------------------------------------
# Stopwords
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


def is_stopword(word: str) -> bool:
    """Check if a word is a function word (stopword)."""
    return word.lower().strip("'\"-") in STOPWORDS


# ---------------------------------------------------------------------------
# Lemmatization
# ---------------------------------------------------------------------------

def simple_lemmatize(word: str) -> list[str]:
    """Generate candidate lemmas by stripping common English suffixes.

    Returns a list of candidate base forms, with the original word first.
    Deduplicates while preserving order.
    """
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


# ---------------------------------------------------------------------------
# API Key Loading
# ---------------------------------------------------------------------------

def load_api_key() -> str:
    """Load the Nous API key from environment or .env file."""
    if os.environ.get("NOUS_API_KEY"):
        return os.environ["NOUS_API_KEY"]
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("NOUS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key. Set NOUS_API_KEY env var or put it in .env", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Database Access
# ---------------------------------------------------------------------------

_DB_CONN = None


def get_db() -> sqlite3.Connection:
    """Return a persistent sqlite3 connection to the WordNet DB."""
    global _DB_CONN
    if _DB_CONN is None:
        if not os.path.exists(WORDNET_DB):
            print(f"ERROR: WordNet DB not found at {WORDNET_DB}", file=sys.stderr)
            sys.exit(1)
        _DB_CONN = sqlite3.connect(WORDNET_DB)
        _DB_CONN.row_factory = sqlite3.Row
        _DB_CONN.execute("PRAGMA journal_mode=WAL")
        _DB_CONN.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return _DB_CONN


# ---------------------------------------------------------------------------
# Standard SQL Queries
# ---------------------------------------------------------------------------

# Look up all senses for a word form (with lemmatization handled by caller)
SENSE_QUERY = """
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

# Get synset info by ILI ID
SYNSET_QUERY = """
    SELECT
        i.id AS ili_id,
        sy.pos AS pos,
        d.definition AS definition
    FROM ilis i
    JOIN synsets sy ON sy.ili_rowid = i.rowid
    JOIN definitions d ON d.synset_rowid = sy.rowid
    WHERE i.id = ?
"""

# Get all lemmas for a synset
SYNSET_LEMMAS_QUERY = """
    SELECT DISTINCT f.form
    FROM synsets sy
    JOIN ilis i ON sy.ili_rowid = i.rowid
    JOIN senses s ON s.synset_rowid = sy.rowid
    JOIN entries e ON s.entry_rowid = e.rowid
    JOIN forms f ON f.entry_rowid = e.rowid
    WHERE i.id = ?
"""

# Get synset relations
SYNSET_RELATIONS_QUERY = """
    SELECT
        rt.type AS relation_type,
        i2.id AS target_ili,
        d2.definition AS target_definition
    FROM synsets sy1
    JOIN ilis i1 ON sy1.ili_rowid = i1.rowid
    JOIN synset_relations sr ON sr.source_rowid = sy1.rowid
    JOIN relation_types rt ON sr.type_rowid = rt.rowid
    JOIN synsets sy2 ON sr.target_rowid = sy2.rowid
    JOIN ilis i2 ON sy2.ili_rowid = i2.rowid
    LEFT JOIN definitions d2 ON d2.synset_rowid = sy2.rowid
    WHERE i1.id = ?
    LIMIT 20
"""

# Get word forms for an ILI
ILI_WORD_FORMS_QUERY = """
    SELECT DISTINCT f.form
    FROM ilis i JOIN synsets sy ON sy.ili_rowid = i.rowid
    JOIN senses s ON s.synset_rowid = sy.rowid
    JOIN entries e ON s.entry_rowid = e.rowid
    JOIN forms f ON f.entry_rowid = e.rowid
    WHERE i.id = ?
    ORDER BY s.entry_rank LIMIT ?
"""

# Get definition for an ILI
ILI_DEFINITION_QUERY = """
    SELECT d.definition FROM ilis i
    JOIN synsets sy ON sy.ili_rowid = i.rowid
    JOIN definitions d ON d.synset_rowid = sy.rowid
    WHERE i.id = ? LIMIT 1
"""


def lookup_word_db(word: str, pos: str | None = None) -> list[dict]:
    """Look up all senses of a word in WordNet, with lemmatization."""
    conn = get_db()
    candidates = simple_lemmatize(word)

    for candidate in candidates:
        query = SENSE_QUERY
        params = [candidate]
        if pos:
            query += " AND e.pos = ?"
            params.append(pos)
        query += " ORDER BY s.entry_rank, s.synset_rank LIMIT 30"

        rows = conn.execute(query, params).fetchall()
        if rows:
            return [_format_sense(r) for r in rows]

    return []


def lookup_phrase_db(phrase: str) -> list[dict]:
    """Look up a multi-word phrase in WordNet."""
    conn = get_db()
    query = SENSE_QUERY + " ORDER BY s.entry_rank, s.synset_rank LIMIT 20"
    rows = conn.execute(query, [phrase]).fetchall()
    return [_format_sense(r) for r in rows]


def get_synset_db(ili_id: str) -> dict | None:
    """Get full synset details by ILI ID."""
    conn = get_db()
    if not ili_id.startswith("i"):
        ili_id = f"i{ili_id}"

    row = conn.execute(SYNSET_QUERY, [ili_id]).fetchone()
    if not row:
        return None

    lemmas = [r["form"] for r in conn.execute(SYNSET_LEMMAS_QUERY, [ili_id]).fetchall()]

    relations = {}
    for r in conn.execute(SYNSET_RELATIONS_QUERY, [ili_id]).fetchall():
        rel_type = r["relation_type"]
        if rel_type not in relations:
            relations[rel_type] = []
        relations[rel_type].append({
            "ili_id": r["target_ili"],
            "definition": r["target_definition"],
        })

    ili_num = int(ili_id[1:])
    return {
        "ili_id": ili_id,
        "ili_num": ili_num,
        "ili_token": internal_ili_token(ili_num),
        "pos": row["pos"],
        "definition": row["definition"],
        "lemmas": lemmas,
        "relations": relations,
    }


def search_definitions_db(query_text: str) -> list[dict]:
    """Search synset definitions by keywords."""
    conn = get_db()
    words = [w.strip() for w in query_text.lower().split() if len(w.strip()) > 2]
    if not words:
        return []

    where_clauses = []
    params = []
    for w in words[:5]:
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
    return [_format_sense(r) for r in rows]


def _format_sense(row) -> dict:
    """Format a database row into a standardized sense dict."""
    ili_num = int(row["ili_id"][1:])
    return {
        "ili_id": row["ili_id"],
        "ili_num": ili_num,
        "ili_token": internal_ili_token(ili_num),
        "pos": row["pos"],
        "definition": row["definition"],
        "form": row["form"] if "form" in row.keys() else "",
    }


# ---------------------------------------------------------------------------
# API Calling
# ---------------------------------------------------------------------------

API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
MODEL = "Hermes-4-405B"
DEFAULT_TIMEOUT = 180
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 8192


def call_hermes_api(
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Call the Hermes API and return the raw message dict from the response."""
    import json
    import urllib.request

    api_key = load_api_key()

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
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

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]
