#!/usr/bin/env python3
"""
WordNet MCP Server (stdio transport)

An MCP server exposing WordNet lookup tools via stdio.
Hermes Agent connects to this and registers the tools natively.

Tools:
- lookup_word: Look up all senses of a word by lemma + optional POS
- lookup_phrase: Look up multi-word expressions
- get_synset: Get synset details by ILI ID
- search_definitions: Search synset definitions by keyword

Usage:
    python wordnet_mcp_server_stdio.py
    # Reads/writes JSON-RPC messages on stdin/stdout
"""

import os
import sqlite3
import sys
from pathlib import Path

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")

# ---------------------------------------------------------------------------
# Lemmatizer
# ---------------------------------------------------------------------------

def simple_lemmatize(word: str) -> list[str]:
    """Generate candidate lemmas by stripping common English suffixes."""
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

# ---------------------------------------------------------------------------
# Database (persistent connection)
# ---------------------------------------------------------------------------

_db_conn = None

def get_db():
    """Return a persistent sqlite3 connection to the WordNet DB."""
    global _db_conn
    if _db_conn is None:
        if not os.path.exists(WORDNET_DB):
            raise RuntimeError(f"WordNet DB not found at {WORDNET_DB}")
        _db_conn = sqlite3.connect(WORDNET_DB)
        _db_conn.row_factory = sqlite3.Row
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA cache_size=-64000")
    return _db_conn

# ---------------------------------------------------------------------------
# WordNet Query Functions
# ---------------------------------------------------------------------------

def lookup_word(word: str, pos: str | None = None) -> list[dict]:
    """Look up all senses of a word, return ILI IDs + definitions."""
    conn = get_db()
    candidates = simple_lemmatize(word)
    results = []
    seen = set()
    
    for lemma in candidates:
        if pos:
            rows = conn.execute("""
                SELECT DISTINCT i.id as ili, e.pos, d.definition 
                FROM forms f
                JOIN entries e ON e.rowid = f.entry_rowid
                JOIN senses s ON s.entry_rowid = e.rowid
                JOIN synsets sy ON sy.rowid = s.synset_rowid
                JOIN ilis i ON i.rowid = sy.ili_rowid
                LEFT JOIN definitions d ON d.synset_rowid = sy.rowid
                WHERE f.form = ? AND e.pos = ?
                ORDER BY e.pos, s.synset_rank
            """, (lemma, pos)).fetchall()
        else:
            rows = conn.execute("""
                SELECT DISTINCT i.id as ili, e.pos, d.definition 
                FROM forms f
                JOIN entries e ON e.rowid = f.entry_rowid
                JOIN senses s ON s.entry_rowid = e.rowid
                JOIN synsets sy ON sy.rowid = s.synset_rowid
                JOIN ilis i ON i.rowid = sy.ili_rowid
                LEFT JOIN definitions d ON d.synset_rowid = sy.rowid
                WHERE f.form = ?
                ORDER BY e.pos, s.synset_rank
            """, (lemma,)).fetchall()
        
        for row in rows:
            key = (row["ili"], row["pos"])
            if key not in seen:
                seen.add(key)
                results.append({
                    "ili": row["ili"],
                    "pos": row["pos"],
                    "definition": row["definition"] or ""
                })
    return results

def lookup_phrase(words: list[str]) -> list[dict]:
    """Look up multi-word expressions."""
    conn = get_db()
    phrase = " ".join(words).lower()
    rows = conn.execute("""
        SELECT DISTINCT i.id as ili, e.pos, d.definition 
        FROM forms f
        JOIN entries e ON e.rowid = f.entry_rowid
        JOIN senses s ON s.entry_rowid = e.rowid
        JOIN synsets sy ON sy.rowid = s.synset_rowid
        JOIN ilis i ON i.rowid = sy.ili_rowid
        LEFT JOIN definitions d ON d.synset_rowid = sy.rowid
        WHERE f.form = ?
        ORDER BY e.pos, s.synset_rank
    """, (phrase,)).fetchall()
    
    return [
        {"ili": row["ili"], "pos": row["pos"], "definition": row["definition"] or ""}
        for row in rows
    ]

def get_synset(ili: str) -> dict | None:
    """Get synset details by ILI ID."""
    conn = get_db()
    # Handle various ILI formats
    ili_clean = ili.replace("ILI_", "").replace("<|", "").replace("|>", "").replace("i", "")
    ili_formatted = f"i{ili_clean}"
    
    # Get synset info + definition
    row = conn.execute("""
        SELECT i.id as ili, sy.pos, i.definition, sy.id as synset_id
        FROM ilis i
        JOIN synsets sy ON sy.ili_rowid = i.rowid
        WHERE i.id = ?
        LIMIT 1
    """, (ili_formatted,)).fetchone()
    
    if not row:
        return None
    
    # Get all lemmas (forms) for this synset
    lemma_rows = conn.execute("""
        SELECT DISTINCT f.form
        FROM forms f
        JOIN entries e ON e.rowid = f.entry_rowid
        JOIN senses s ON s.entry_rowid = e.rowid
        WHERE s.synset_rowid = ?
        ORDER BY s.entry_rank, f.rank
    """, (row["synset_id"],)).fetchall()
    
    lemmas = [r["form"] for r in lemma_rows]
    
    # Get hypernyms (broader terms)
    hypernym_rows = conn.execute("""
        SELECT i.id as ili, e.pos
        FROM synset_relations sr
        JOIN synsets sy ON sy.rowid = sr.target_rowid
        JOIN ilis i ON i.rowid = sy.ili_rowid
        JOIN entries e ON e.rowid = (
            SELECT entry_rowid FROM senses WHERE synset_rowid = sy.rowid LIMIT 1
        )
        WHERE sr.source_rowid = ? AND sr.type_rowid = (
            SELECT rowid FROM relation_types WHERE type = 'hypernym'
        )
    """, (row["synset_id"],)).fetchall()
    
    hypernyms = [{"ili": r["ili"], "pos": r["pos"]} for r in hypernym_rows]
    
    # Get hyponyms (narrower terms)
    hyponym_rows = conn.execute("""
        SELECT i.id as ili, e.pos
        FROM synset_relations sr
        JOIN synsets sy ON sy.rowid = sr.target_rowid
        JOIN ilis i ON i.rowid = sy.ili_rowid
        JOIN entries e ON e.rowid = (
            SELECT entry_rowid FROM senses WHERE synset_rowid = sy.rowid LIMIT 1
        )
        WHERE sr.source_rowid = ? AND sr.type_rowid = (
            SELECT rowid FROM relation_types WHERE type = 'hyponym'
        )
    """, (row["synset_id"],)).fetchall()
    
    hyponyms = [{"ili": r["ili"], "pos": r["pos"]} for r in hyponym_rows]
    
    return {
        "ili": row["ili"],
        "pos": row["pos"],
        "definition": row["definition"] or "",
        "lemmas": lemmas,
        "hypernyms": hypernyms,
        "hyponyms": hyponyms
    }

def search_definitions(query: str) -> list[dict]:
    """Search synset definitions by keyword."""
    conn = get_db()
    words = query.split()
    if not words:
        return []
    
    # Search in ILI definitions
    patterns = [f"%{w}%" for w in words]
    placeholders = " OR ".join(["i.definition LIKE ?"] * len(words))
    
    rows = conn.execute(f"""
        SELECT DISTINCT i.id as ili, sy.pos, i.definition
        FROM ilis i
        JOIN synsets sy ON sy.ili_rowid = i.rowid
        WHERE {placeholders}
        LIMIT 20
    """, patterns).fetchall()
    
    return [
        {"ili": row["ili"], "pos": row["pos"], "definition": row["definition"]}
        for row in rows
    ]

# ---------------------------------------------------------------------------
# MCP Server Setup
# ---------------------------------------------------------------------------

app = Server("wordnet")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="lookup_word",
            description="Look up all WordNet senses for a word. Returns ILI IDs, POS tags, and definitions. Use this to find candidate meanings before disambiguation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "The word to look up (e.g., 'bank', 'run')"},
                    "pos": {"type": "string", "description": "Optional part of speech: 'n' (noun), 'v' (verb), 'a' (adjective), 'r' (adverb)"}
                },
                "required": ["word"]
            }
        ),
        Tool(
            name="lookup_phrase",
            description="Look up multi-word expressions like 'credit card' or 'orange juice'. Returns ILI IDs if found.",
            inputSchema={
                "type": "object",
                "properties": {
                    "words": {"type": "array", "items": {"type": "string"}, "description": "List of words in the phrase (e.g., ['credit', 'card'])"}
                },
                "required": ["words"]
            }
        ),
        Tool(
            name="get_synset",
            description="Get full details for a synset by its ILI ID. Returns definition, POS, lemmas (synonyms), hypernyms (broader), and hyponyms (narrower). Use this for comprehensive synset research.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ili": {"type": "string", "description": "ILI ID like 'i35152', 'ILI_035152', or just '35152'"}
                },
                "required": ["ili"]
            }
        ),
        Tool(
            name="search_definitions",
            description="Search synset definitions by keywords. Returns matching synsets with their ILI IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms (e.g., 'financial institution')"}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    import json
    
    if name == "lookup_word":
        results = lookup_word(arguments["word"], arguments.get("pos"))
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    elif name == "lookup_phrase":
        results = lookup_phrase(arguments["words"])
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    elif name == "get_synset":
        result = get_synset(arguments["ili"])
        return [TextContent(type="text", text=json.dumps(result, indent=2) if result else "null")]
    
    elif name == "search_definitions":
        results = search_definitions(arguments["query"])
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    if not os.path.exists(WORDNET_DB):
        print(f"ERROR: WordNet DB not found at {WORDNET_DB}", file=sys.stderr)
        print("Download it with: python3 -c 'import wn; wn.download(\"ewn:2020\")'", file=sys.stderr)
        sys.exit(1)
    
    # Pre-warm DB connection
    get_db()
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
