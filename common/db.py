import sqlite3
import time
from datetime import date

from .config import DATA


class Store:
    """Per-bot SQLite store: premium, bought credits and daily free usage."""

    def __init__(self, name: str):
        DATA.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(DATA / f"{name}.sqlite3")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                premium_until INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 0,
                used_day TEXT DEFAULT '',
                used INTEGER DEFAULT 0,
                created INTEGER
            );
            CREATE TABLE IF NOT EXISTS payments (
                charge_id TEXT PRIMARY KEY,
                user_id INTEGER,
                stars INTEGER,
                payload TEXT,
                at INTEGER
            );
            """
        )

    def _user(self, uid: int) -> tuple:
        self.conn.execute(
            "INSERT OR IGNORE INTO users (id, created) VALUES (?, ?)", (uid, int(time.time()))
        )
        return self.conn.execute(
            "SELECT premium_until, credits, used_day, used FROM users WHERE id = ?", (uid,)
        ).fetchone()

    def is_premium(self, uid: int) -> bool:
        return self._user(uid)[0] > time.time()

    def add_premium(self, uid: int, days: int) -> None:
        until = max(self._user(uid)[0], int(time.time())) + days * 86400
        self.conn.execute("UPDATE users SET premium_until = ? WHERE id = ?", (until, uid))
        self.conn.commit()

    def add_credits(self, uid: int, n: int) -> None:
        self._user(uid)
        self.conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (n, uid))
        self.conn.commit()

    def credits(self, uid: int) -> int:
        return self._user(uid)[1]

    def take(self, uid: int, free_per_day: int) -> bool:
        """Spend one use: premium is unlimited, then free daily quota, then bought credits."""
        premium_until, credits, used_day, used = self._user(uid)
        if premium_until > time.time():
            return True
        today = date.today().isoformat()
        if used_day != today:
            used = 0
        if used < free_per_day:
            self.conn.execute(
                "UPDATE users SET used_day = ?, used = ? WHERE id = ?", (today, used + 1, uid)
            )
        elif credits > 0:
            self.conn.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (uid,))
        else:
            return False
        self.conn.commit()
        return True

    def record_payment(self, charge_id: str, uid: int, stars: int, payload: str) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO payments VALUES (?, ?, ?, ?, ?)",
            (charge_id, uid, stars, payload, int(time.time())),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def stats(self) -> str:
        users = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paid, stars = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(stars), 0) FROM payments"
        ).fetchone()
        return f"users: {users}\npayments: {paid}\nstars: {stars}"
