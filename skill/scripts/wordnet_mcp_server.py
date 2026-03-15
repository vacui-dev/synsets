#!/usr/bin/env python3
"""
WordNet MCP Server — Local HTTP server exposing WordNet as REST endpoints.

Starts once, holds the DB connection open, serves concurrent requests.
Designed for Hermes Agent tool access via curl.

Usage:
    python3 wordnet_mcp_server.py [--port 8741] [--db ~/.wn_data/wn.db]

Endpoints:
    GET /lookup?word=represent         — all senses for a word (auto-lemmatizes)
    GET /lookup?word=represent&pos=v   — filtered by POS (n/v/a/r)
    GET /phrase?words=orange+juice     — multi-word expression lookup
    GET /synset?ili=i35152             — full synset details
    GET /search?q=financial+institution — search definitions
    GET /health                        — server status
"""

import json
import os
import re
import sqlite3
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

WORDNET_DB = os.path.expanduser("~/.wn_data/wn.db")
DEFAULT_PORT = 8741


# ---------------------------------------------------------------------------
# Lemmatizer (same as hermes_tool_use.py)
# ---------------------------------------------------------------------------

def simple_lemmatize(word: str) -> list[str]:
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
    if w.endswith("ies") and len(w) > 5:
        candidates.append(w[:-3] + "y")
    elif w.endswith("es") and len(w) > 4:
        candidates.append(w[:-2])
        candidates.append(w[:-1])
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
# Database queries
# ---------------------------------------------------------------------------

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

SYNSET_LEMMAS_QUERY = """
    SELECT DISTINCT f.form
    FROM synsets sy
    JOIN ilis i ON sy.ili_rowid = i.rowid
    JOIN senses s ON s.synset_rowid = sy.rowid
    JOIN entries e ON s.entry_rowid = e.rowid
    JOIN forms f ON f.entry_rowid = e.rowid
    WHERE i.id = ?
"""

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

DEFINITION_SEARCH_QUERY_TEMPLATE = """
    SELECT DISTINCT
        i.id AS ili_id,
        d.definition AS definition,
        sy.pos AS pos
    FROM definitions d
    JOIN synsets sy ON d.synset_rowid = sy.rowid
    JOIN ilis i    ON sy.ili_rowid = i.rowid
    WHERE {where}
    LIMIT 10
"""


def format_sense(row) -> dict:
    ili_num = int(row["ili_id"][1:])
    return {
        "ili_id": row["ili_id"],
        "ili_num": ili_num,
        "ili_token": f"<|i{ili_num}|>",
        "pos": row["pos"],
        "definition": row["definition"],
        "form": row["form"] if "form" in row.keys() else "",
    }


class WordNetDB:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA cache_size=-64000")

        # Count stats
        self.synset_count = self.conn.execute("SELECT COUNT(*) FROM synsets").fetchone()[0]
        self.ili_count = self.conn.execute("SELECT COUNT(*) FROM ilis").fetchone()[0]

    def lookup_word(self, word: str, pos: str = None) -> list[dict]:
        candidates = simple_lemmatize(word)
        for candidate in candidates:
            query = SENSE_QUERY
            params = [candidate]
            if pos:
                query += " AND e.pos = ?"
                params.append(pos)
            query += " ORDER BY s.entry_rank, s.synset_rank LIMIT 30"
            rows = self.conn.execute(query, params).fetchall()
            if rows:
                return [format_sense(r) for r in rows]
        return []

    def lookup_phrase(self, phrase: str) -> list[dict]:
        query = SENSE_QUERY + " ORDER BY s.entry_rank, s.synset_rank LIMIT 20"
        rows = self.conn.execute(query, [phrase]).fetchall()
        return [format_sense(r) for r in rows]

    def get_synset(self, ili_id: str) -> dict | None:
        if not ili_id.startswith("i"):
            ili_id = f"i{ili_id}"

        row = self.conn.execute(SYNSET_QUERY, [ili_id]).fetchone()
        if not row:
            return None

        lemmas = [r["form"] for r in self.conn.execute(SYNSET_LEMMAS_QUERY, [ili_id]).fetchall()]
        relations = {}
        for r in self.conn.execute(SYNSET_RELATIONS_QUERY, [ili_id]).fetchall():
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
            "ili_token": f"<|i{ili_num}|>",
            "pos": row["pos"],
            "definition": row["definition"],
            "lemmas": lemmas,
            "relations": relations,
        }

    def search_definitions(self, query_text: str) -> list[dict]:
        words = [w.strip() for w in query_text.lower().split() if len(w.strip()) > 2]
        if not words:
            return []

        where_clauses = []
        params = []
        for w in words[:5]:
            where_clauses.append("LOWER(d.definition) LIKE ?")
            params.append(f"%{w}%")

        query = DEFINITION_SEARCH_QUERY_TEMPLATE.format(where=" AND ".join(where_clauses))
        rows = self.conn.execute(query, params).fetchall()

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
# HTTP Handler
# ---------------------------------------------------------------------------

db: WordNetDB = None  # Set at startup


class MCPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        try:
            if parsed.path == "/health":
                result = {"status": "ok", "synsets": db.synset_count, "ilis": db.ili_count}
            elif parsed.path == "/lookup":
                word = params.get("word", [""])[0]
                pos = params.get("pos", [None])[0]
                if not word:
                    self._error(400, "Missing 'word' parameter")
                    return
                result = db.lookup_word(word, pos)
            elif parsed.path == "/phrase":
                words = params.get("words", [""])[0]
                if not words:
                    self._error(400, "Missing 'words' parameter")
                    return
                result = db.lookup_phrase(words.replace("+", " "))
            elif parsed.path == "/synset":
                ili = params.get("ili", [""])[0]
                if not ili:
                    self._error(400, "Missing 'ili' parameter")
                    return
                result = db.get_synset(ili)
                if result is None:
                    self._error(404, f"Synset {ili} not found")
                    return
            elif parsed.path == "/search":
                q = params.get("q", [""])[0]
                if not q:
                    self._error(400, "Missing 'q' parameter")
                    return
                result = db.search_definitions(q.replace("+", " "))
            else:
                self._error(404, f"Unknown endpoint: {parsed.path}")
                return

            self._json_response(200, result)

        except Exception as e:
            self._error(500, str(e))

    def _json_response(self, code: int, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str):
        self._json_response(code, {"error": message})

    def log_message(self, format, *args):
        # Suppress default access logging
        pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="WordNet MCP Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default=WORDNET_DB)
    args = parser.parse_args()

    global db
    print(f"Loading WordNet DB from {args.db}...")
    db = WordNetDB(args.db)
    print(f"  {db.synset_count} synsets, {db.ili_count} ILIs loaded")

    server = ThreadedHTTPServer(("0.0.0.0", args.port), MCPHandler)
    print(f"WordNet MCP Server running at http://localhost:{args.port}")
    print(f"Endpoints: /lookup, /phrase, /synset, /search, /health")
    print(f"Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
