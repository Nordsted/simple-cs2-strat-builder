import json
import os
import sqlite3
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
STRATS_DIR = BASE_DIR / "strats"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "strats.db"))
PORT = int(os.getenv("PORT", "8080"))

NUMPAD_KEYS = {
    "1": "KP_END",
    "2": "KP_DOWNARROW",
    "3": "KP_PGDN",
    "4": "KP_LEFTARROW",
    "5": "KP_5",
    "6": "KP_RIGHTARROW",
    "7": "KP_HOME",
    "8": "KP_UPARROW",
    "9": "KP_PGUP",
}

STRATEGIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_slug TEXT NOT NULL REFERENCES maps(slug),
    side TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    creator TEXT NOT NULL DEFAULT 'System',
    source TEXT NOT NULL DEFAULT 'database',
    message TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS maps (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        ensure_strategy_schema(conn)
        seed_data(conn)


def ensure_strategy_schema(conn):
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(strategies)").fetchall()
    }
    if not columns:
        conn.execute(STRATEGIES_TABLE_SQL)
        return
    if "message" in columns and "meta_json" in columns and "bindings_json" not in columns:
        return

    conn.execute("ALTER TABLE strategies RENAME TO strategies_legacy")
    conn.execute(STRATEGIES_TABLE_SQL)

    legacy_rows = conn.execute("SELECT * FROM strategies_legacy ORDER BY id").fetchall()
    for row in legacy_rows:
        message = ""
        if "bindings_json" in columns:
            message = extract_message_from_bindings(row["bindings_json"])
        if not message and "message" in columns:
            message = normalize_strategy_message(row["message"])
        meta_json = row["meta_json"] if "meta_json" in columns else "{}"
        conn.execute(
            """
            INSERT INTO strategies(
                id, map_slug, side, name, description, creator, source, message, meta_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["map_slug"],
                row["side"],
                row["name"],
                row["description"],
                row["creator"],
                row["source"],
                message or row["name"],
                normalize_meta_json(meta_json),
                row["created_at"],
            ),
        )

    conn.execute("DROP TABLE strategies_legacy")


def extract_message_from_bindings(raw_bindings):
    try:
        bindings = json.loads(raw_bindings)
    except (TypeError, json.JSONDecodeError):
        return ""

    for slot in sorted(bindings, key=lambda key: int(str(key)) if str(key).isdigit() else 999):
        message = normalize_strategy_message(bindings[slot])
        if message:
            return message
    return ""


def normalize_meta_json(raw_meta):
    try:
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
    except json.JSONDecodeError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return json.dumps(meta, sort_keys=True)


def is_strategy_seed_file(strategy_file):
    return strategy_file.name != "strats_baseline.json"



def load_strategy_file_paths():
    strategy_files = sorted(
        strategy_file
        for strategy_file in STRATS_DIR.glob("*.json")
        if is_strategy_seed_file(strategy_file)
    )
    if not strategy_files:
        raise FileNotFoundError(f"No strategy seed files found in {STRATS_DIR}")
    return strategy_files


def read_strategy_seed(strategy_file):
    payload = json.loads(strategy_file.read_text(encoding="utf-8"))
    map_slug = str(payload.get("mapSlug", "")).strip().lower()
    map_name = str(payload.get("mapName", "")).strip()
    strategies = payload.get("strategies", [])

    if not map_slug or not map_name or not isinstance(strategies, list):
        raise ValueError(f"Invalid strategy file: {strategy_file.name}")

    return {
        "mapSlug": map_slug,
        "mapName": map_name,
        "source": strategy_file.name,
        "strategies": strategies,
    }


def ensure_map(conn, map_slug, map_name):
    conn.execute(
        "INSERT OR IGNORE INTO maps(slug, name) VALUES (?, ?)",
        (map_slug, map_name),
    )


def seed_data(conn):
    existing = conn.execute("SELECT COUNT(*) AS count FROM strategies").fetchone()["count"]
    if existing:
        return

    for strategy_file in load_strategy_file_paths():
        seed = read_strategy_seed(strategy_file)
        ensure_map(conn, seed["mapSlug"], seed["mapName"])

        for strategy in seed["strategies"]:
            insert_strategy(
                conn,
                {
                    "mapSlug": seed["mapSlug"],
                    "side": strategy.get("side"),
                    "name": strategy.get("name"),
                    "description": strategy.get("description"),
                    "message": strategy.get("message"),
                    "creator": strategy.get("creator", "System"),
                    "meta": strategy.get("meta", {}),
                    "source": seed["source"],
                },
            )


def sanitize_command(command):
    return " ".join(str(command).strip().split())


def strip_team_chat_prefix(command):
    normalized = sanitize_command(command)
    if normalized.lower().startswith("say_team "):
        return normalized[9:].strip()
    return normalized


def normalize_strategy_message(message):
    return strip_team_chat_prefix(message)


def validate_strategy(payload):
    map_slug = str(payload.get("mapSlug", "")).strip().lower()
    side = str(payload.get("side", "")).strip().upper()
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    message = normalize_strategy_message(payload.get("message", ""))
    creator = str(payload.get("creator", "")).strip() or "Community"
    source = str(payload.get("source", "database")).strip() or "database"
    meta = payload.get("meta", {})

    if not map_slug or not name or not description or not message:
        raise ValueError("Map, side, name, description, and message are required.")
    if side not in {"T", "CT"}:
        raise ValueError("Side must be T or CT.")
    if not isinstance(meta, dict):
        raise ValueError("Meta must be an object.")

    return {
        "mapSlug": map_slug,
        "side": side,
        "name": name,
        "description": description,
        "message": message,
        "creator": creator,
        "source": source,
        "meta": meta,
    }


def build_command(messages):
    commands = []
    for index, message in enumerate(messages[:9], start=1):
        normalized_message = normalize_strategy_message(message)
        if not normalized_message:
            continue
        escaped_message = normalized_message.replace('"', "'")
        commands.append(f'bind {NUMPAD_KEYS[str(index)]} "say_team {escaped_message}"')
    return "; ".join(commands)


def serialize_strategy(row):
    return {
        "id": row["id"],
        "mapSlug": row["map_slug"],
        "side": row["side"],
        "name": row["name"],
        "description": row["description"],
        "message": normalize_strategy_message(row["message"]),
        "creator": row["creator"],
        "source": row["source"],
        "meta": json.loads(row["meta_json"]),
    }


def insert_strategy(conn, payload):
    strategy = validate_strategy(payload)
    cursor = conn.execute(
        """
        INSERT INTO strategies(map_slug, side, name, description, creator, source, message, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy["mapSlug"],
            strategy["side"],
            strategy["name"],
            strategy["description"],
            strategy["creator"],
            strategy["source"],
            strategy["message"],
            json.dumps(strategy["meta"], sort_keys=True),
        ),
    )
    row = conn.execute("SELECT * FROM strategies WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return serialize_strategy(row)


def list_maps(conn):
    rows = conn.execute("SELECT slug, name FROM maps ORDER BY name").fetchall()
    return [{"slug": row["slug"], "name": row["name"]} for row in rows]


def list_strategies(conn):
    rows = conn.execute(
        "SELECT * FROM strategies ORDER BY map_slug, side, id"
    ).fetchall()
    return [serialize_strategy(row) for row in rows]


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_HEAD(self):
        if self.handle_json_get(send_body=False):
            return
        if urlparse(self.path).path == "/":
            self.path = "/index.html"
        return super().do_HEAD()

    def do_GET(self):
        if self.handle_json_get(send_body=True):
            return
        if urlparse(self.path).path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def handle_json_get(self, send_body):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.write_json({"status": "ok"}, send_body=send_body)
            return True
        if parsed.path == "/api/data":
            with get_connection() as conn:
                self.write_json(
                    {"maps": list_maps(conn), "strategies": list_strategies(conn)},
                    send_body=send_body,
                )
            return True
        return False

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/strategies":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            with get_connection() as conn:
                strategy = insert_strategy(conn, payload)
                conn.commit()
            self.write_json(strategy, status=HTTPStatus.CREATED)
        except json.JSONDecodeError:
            self.write_json({"error": "Invalid JSON."}, status=HTTPStatus.BAD_REQUEST)
        except ValueError as error:
            self.write_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)

    def write_json(self, payload, status=HTTPStatus.OK, send_body=True):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)


def create_server():
    init_db()
    return ThreadingHTTPServer(("0.0.0.0", PORT), AppHandler)


if __name__ == "__main__":
    server = create_server()
    print(f"Server listening on :{PORT}")
    server.serve_forever()
