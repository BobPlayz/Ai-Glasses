import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from laptop.memory.store import search_memories


class MemorySearchTests(unittest.TestCase):
    def test_returns_keyword_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT, created_at TEXT)")
                    db.executemany(
                        "INSERT INTO memories (content, created_at) VALUES (?, ?)",
                        [
                            ("The science exhibition is on October 22", "1"),
                            ("I prefer short spoken answers", "2"),
                            ("The camera has a privacy switch", "3"),
                        ],
                    )
            self.assertIn("The science exhibition is on October 22", search_memories(path, "When is the exhibition?"))

    def test_empty_query_returns_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT, created_at TEXT)")
            self.assertEqual([], search_memories(path, "a is"))


if __name__ == "__main__":
    unittest.main()
