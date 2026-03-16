#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/home/ubt18/.wn_data/wn.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get synset info for ILI 3856
cursor.execute("""
    SELECT i.id as ili, sy.pos, d.definition, sy.rowid as synset_rowid
    FROM ilis i
    JOIN synsets sy ON sy.ili_rowid = i.rowid
    LEFT JOIN definitions d ON d.synset_rowid = sy.rowid
    WHERE i.id = ?
    LIMIT 1
""", ('i3856',))

row = cursor.fetchone()
if row:
    print(f"ILI: {row['ili']}")
    print(f"POS: {row['pos']}")
    print(f"Definition: {row['definition']}")
    synset_rowid = row['synset_rowid']
    
    # Get lemmas
    cursor.execute("""
        SELECT DISTINCT f.form
        FROM forms f
        JOIN entries e ON e.rowid = f.entry_rowid
        JOIN senses s ON s.entry_rowid = e.rowid
        WHERE s.synset_rowid = ?
        ORDER BY s.entry_rank, f.rank
    """, (synset_rowid,))
    
    lemmas = [r['form'] for r in cursor.fetchall()]
    print(f"Lemmas: {lemmas}")
    
    # Get hypernyms
    cursor.execute("""
        SELECT i.id as ili, tgt.pos
        FROM synset_relations sr
        JOIN synsets tgt ON tgt.rowid = sr.target_rowid
        JOIN ilis i ON i.rowid = tgt.ili_rowid
        JOIN relation_types rt ON rt.rowid = sr.type_rowid
        WHERE sr.source_rowid = ? AND rt.type = 'hypernym'
    """, (synset_rowid,))
    
    hypernyms = [(r['ili'], r['pos']) for r in cursor.fetchall()]
    print(f"Hypernyms: {hypernyms}")
    
    # Get hyponyms
    cursor.execute("""
        SELECT i.id as ili, src.pos
        FROM synset_relations sr
        JOIN synsets src ON src.rowid = sr.source_rowid
        JOIN ilis i ON i.rowid = src.ili_rowid
        JOIN relation_types rt ON rt.rowid = sr.type_rowid
        WHERE sr.target_rowid = ? AND rt.type = 'hypernym'
    """, (synset_rowid,))
    
    hyponyms = [(r['ili'], r['pos']) for r in cursor.fetchall()]
    print(f"Hyponyms: {hyponyms[:5]}")  # First 5
else:
    print("Synset not found")
