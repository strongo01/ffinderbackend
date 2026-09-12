#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path

source = Path(sys.argv[1])
output = Path(sys.argv[2])
if output.exists():
    output.unlink()
conn = sqlite3.connect(output)
conn.execute("PRAGMA journal_mode=OFF")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("PRAGMA temp_store=MEMORY")
conn.executescript('''
CREATE TABLE products (
  barcode TEXT PRIMARY KEY,
  product_name TEXT,
  generic_name TEXT,
  brands TEXT,
  quantity TEXT,
  serving_size TEXT,
  nutriscore TEXT,
  energy_kcal REAL,
  fat REAL,
  saturated_fat REAL,
  carbohydrates REAL,
  sugars REAL,
  fiber REAL,
  proteins REAL,
  salt REAL,
  ingredients TEXT,
  vegan INTEGER NOT NULL DEFAULT 0,
  vegetarian INTEGER NOT NULL DEFAULT 0,
  image_url TEXT
);
CREATE VIRTUAL TABLE products_fts USING fts5(
  barcode UNINDEXED,
  product_name,
  generic_name,
  brands,
  content='products',
  content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
''')
insert = conn.execute
rows = []
count = 0
with source.open(encoding="utf-8") as f:
    for line in f:
        p = json.loads(line)
        rows.append(tuple(p.get(k) for k in (
            "barcode", "product_name", "generic_name", "brands", "quantity",
            "serving_size", "nutriscore", "energy_kcal", "fat", "saturated_fat",
            "carbohydrates", "sugars", "fiber", "proteins", "salt", "ingredients"
        )) + (int(bool(p.get("vegan"))), int(bool(p.get("vegetarian"))), p.get("image_url")))
        if len(rows) >= 1000:
            conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            rows.clear()
        count += 1
if rows:
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
conn.execute("CREATE INDEX idx_products_name ON products(product_name)")
conn.execute("ANALYZE")
conn.commit()
conn.execute("PRAGMA journal_mode=DELETE")
conn.close()
print(json.dumps({"count": count, "output": str(output), "bytes": output.stat().st_size}))
