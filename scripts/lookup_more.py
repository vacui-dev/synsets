#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/home/ubt18/.wn_data/wn.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

words_to_lookup = [
    ('difficult', 'a'),
    ('external', 'a'),
    ('stimuli', 'n'),
    ('restore', 'v'),
    ('recovery', 'n'),
    ('cognitive', 'a'),
    ('function', 'n'),
    ('professional', 'n'),
    ('assess', 'v'),
    ('patient', 'n'),
    ('phase', 'n'),
    ('cycle', 'n'),
]

for word, pos in words_to_lookup:
    cursor.execute("""
        SELECT DISTINCT i.id as ili, e.pos, d.definition 
        FROM forms f
        JOIN entries e ON e.rowid = f.entry_rowid
        JOIN senses s ON s.entry_rowid = e.rowid
        JOIN synsets sy ON sy.rowid = s.synset_rowid
        JOIN ilis i ON i.rowid = sy.ili_rowid
        LEFT JOIN definitions d ON d.synset_rowid = sy.rowid
        WHERE f.form = ? AND e.pos = ?
        ORDER BY e.pos, s.synset_rank
        LIMIT 1
    """, (word, pos))
    
    row = cursor.fetchone()
    if row:
        ili_num = int(row['ili'][1:])
        print(f"{word} ({pos}): ILI_{ili_num:06d}")
    else:
        print(f"{word} ({pos}): NOT FOUND")
