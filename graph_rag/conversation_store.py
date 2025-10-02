# graph_rag/conversation_store.py
import sqlite3
import os

DB = "conversations.db"

def _conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    if not os.path.exists(DB):
        c = _conn()
        c.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, role TEXT, text TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.commit()
        c.close()

def store_message(conversation_id, role, text):
    c = _conn()
    c.execute("INSERT INTO messages (conversation_id, role, text) VALUES (?, ?, ?)", (conversation_id, role, text))
    c.commit()
    c.close()
