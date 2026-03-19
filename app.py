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


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS maps (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                map_slug TEXT NOT NULL REFERENCES maps(slug),
                side TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                creator TEXT NOT NULL DEFAULT 'System',
                source TEXT NOT NULL DEFAULT 'database',
                bindings_json TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        seed_data(conn)


def load_strategy_file_paths():
    strategy_files = sorted(STRATS_DIR.glob("*.json"))
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
                    "creator": strategy.get("creator", "System"),
                    "bindings": strategy.get("bindings", {}),
                    "source": seed["source"],
                },
            )


def sanitize_command(command):
    return " ".join(command.strip().split())


def strip_team_chat_prefix(command):
    normalized = sanitize_command(command)
    if normalized.lower().startswith("say_team "):
        return normalized[9:].strip()
    return normalized


def normalize_binding_command(command):
    return strip_team_chat_prefix(str(command))


def validate_strategy(payload):
    map_slug = str(payload.get("mapSlug", "")).strip().lower()
    side = str(payload.get("side", "")).strip().upper()
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    creator = str(payload.get("creator", "")).strip() or "Community"
    source = str(payload.get("source", "database")).strip() or "database"
    bindings = payload.get("bindings") or {}

    if not map_slug or not name or not description:
        raise ValueError("Map, name, and description are required.")
    if side not in {"T", "CT"}:
        raise ValueError("Side must be T or CT.")
    if not isinstance(bindings, dict):
        raise ValueError("Bindings must be an object.")

    cleaned_bindings = {}
    for slot, raw_command in bindings.items():
        slot_text = str(slot).strip()
        if slot_text not in NUMPAD_KEYS:
            raise ValueError(f"Unknown numpad slot: {slot_text}")
        command = normalize_binding_command(raw_command)
        if command:
            cleaned_bindings[slot_text] = command

    if not cleaned_bindings:
        raise ValueError("At least one valid binding is required.")

    return {
        "mapSlug": map_slug,
        "side": side,
        "name": name,
        "description": description,
        "creator": creator,
        "source": source,
        "bindings": cleaned_bindings,
    }


def build_command(bindings):
    commands = []
    for slot in sorted(bindings, key=int):
        message = normalize_binding_command(bindings[slot]).replace('"', "'")
        commands.append(f'bind {NUMPAD_KEYS[slot]} "say_team {message}"')
    return "; ".join(commands)


def serialize_strategy(row):
    raw_bindings = json.loads(row["bindings_json"])
    bindings = {
        slot: normalize_binding_command(command)
        for slot, command in raw_bindings.items()
        if normalize_binding_command(command)
    }
    return {
        "id": row["id"],
        "mapSlug": row["map_slug"],
        "side": row["side"],
        "name": row["name"],
        "description": row["description"],
        "creator": row["creator"],
        "source": row["source"],
        "bindings": bindings,
        "command": build_command(bindings),
    }


def insert_strategy(conn, payload):
    strategy = validate_strategy(payload)
    cursor = conn.execute(
        """
        INSERT INTO strategies(map_slug, side, name, description, creator, source, bindings_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy["mapSlug"],
            strategy["side"],
            strategy["name"],
            strategy["description"],
            strategy["creator"],
            strategy["source"],
            json.dumps(strategy["bindings"]),
        ),
    )
    row = conn.execute("SELECT * FROM strategies WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return serialize_strategy(row)


def list_maps(conn):
    rows = conn.execute("SELECT slug, name FROM maps ORDER BY name").fetchall()
    return [{"slug": row["slug"], "name": row["name"]} for row in rows]


def list_strategies(conn):
    rows = conn.execute(
        "SELECT * FROM strategies ORDER BY map_slug, side, name"
    ).fetchall()
    return [serialize_strategy(row) for row in rows]


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return self.write_json({"status": "ok"})
        if parsed.path == "/api/data":
            with get_connection() as conn:
                return self.write_json(
                    {"maps": list_maps(conn), "strategies": list_strategies(conn)}
                )
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

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

    def write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server():
    init_db()
    return ThreadingHTTPServer(("0.0.0.0", PORT), AppHandler)


if __name__ == "__main__":
    server = create_server()
    print(f"Server listening on :{PORT}")
    server.serve_forever()
