import json
import tempfile
import unittest
from pathlib import Path

import app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.original_database_path = app.DATABASE_PATH
        self.original_strats_dir = app.STRATS_DIR
        app.DATABASE_PATH = self.root / "data" / "test.db"
        app.STRATS_DIR = self.root / "strats"
        app.STRATS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app.DATABASE_PATH = self.original_database_path
        app.STRATS_DIR = self.original_strats_dir
        self.temp_dir.cleanup()

    def write_seed(self, name, payload):
        (app.STRATS_DIR / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_validate_strategy_requires_message_and_meta_object(self):
        strategy = app.validate_strategy(
            {
                "mapSlug": " Mirage ",
                "side": " ct ",
                "name": " Retake ",
                "description": " Hold site ",
                "message": " say_team   Flash now  ",
                "creator": " Team ",
                "meta": {"pace": "fast"},
            }
        )

        self.assertEqual(strategy["mapSlug"], "mirage")
        self.assertEqual(strategy["side"], "CT")
        self.assertEqual(strategy["creator"], "Team")
        self.assertEqual(strategy["message"], "Flash now")
        self.assertEqual(strategy["meta"], {"pace": "fast"})

        with self.assertRaises(ValueError):
            app.validate_strategy(
                {
                    "mapSlug": "mirage",
                    "side": "T",
                    "name": "Missing message",
                    "description": "No message here",
                }
            )

        with self.assertRaises(ValueError):
            app.validate_strategy(
                {
                    "mapSlug": "mirage",
                    "side": "T",
                    "name": "Bad meta",
                    "description": "Meta must be an object",
                    "message": "Go now",
                    "meta": ["fast"],
                }
            )

    def test_build_command_uses_ordered_message_list(self):
        command = app.build_command(["say_team first", "", 'say_team "mid"', "last"])

        self.assertEqual(
            command,
            'bind KP_END "say_team first"; bind KP_PGDN "say_team \'mid\'"; bind KP_LEFTARROW "say_team last"',
        )

    def test_read_strategy_seed_rejects_invalid_payload(self):
        invalid_file = app.STRATS_DIR / "broken.json"
        invalid_file.write_text(json.dumps({"mapSlug": "mirage", "strategies": []}), encoding="utf-8")

        with self.assertRaises(ValueError):
            app.read_strategy_seed(invalid_file)

    def test_init_db_seeds_message_first_schema_and_serializes_meta(self):
        self.write_seed(
            "mirage.json",
            {
                "mapSlug": "mirage",
                "mapName": "Mirage",
                "strategies": [
                    {
                        "side": "T",
                        "name": "A split",
                        "description": "Split A from mid and ramp.",
                        "message": "smoke window and split A",
                        "meta": {"pace": "fast", "nades": 2},
                    }
                ],
            },
        )
        self.write_seed(
            "inferno.json",
            {
                "mapSlug": "inferno",
                "mapName": "Inferno",
                "strategies": [
                    {
                        "side": "CT",
                        "name": "Banana hold",
                        "description": "Delay banana with utility.",
                        "message": "molly banana and play anti-flash",
                        "creator": "Coach",
                    }
                ],
            },
        )

        app.init_db()

        with app.get_connection() as conn:
            maps = app.list_maps(conn)
            strategies = app.list_strategies(conn)

        self.assertEqual([entry["slug"] for entry in maps], ["inferno", "mirage"])
        self.assertEqual(len(strategies), 2)
        self.assertEqual(strategies[0]["message"], "molly banana and play anti-flash")
        self.assertEqual(strategies[0]["meta"], {})
        self.assertNotIn("bindings", strategies[0])
        self.assertNotIn("command", strategies[0])
        self.assertEqual(strategies[1]["meta"], {"nades": 2, "pace": "fast"})

    def test_insert_strategy_defaults_source_and_serializes_without_slot_data(self):
        self.write_seed(
            "mirage.json",
            {
                "mapSlug": "mirage",
                "mapName": "Mirage",
                "strategies": [],
            },
        )
        app.init_db()

        with app.get_connection() as conn:
            strategy = app.insert_strategy(
                conn,
                {
                    "mapSlug": "mirage",
                    "side": "CT",
                    "name": "B retake",
                    "description": "Retake together through market.",
                    "message": "group market",
                    "meta": {"spawn": "market"},
                },
            )
            conn.commit()

        self.assertEqual(strategy["source"], "database")
        self.assertEqual(strategy["message"], "group market")
        self.assertEqual(strategy["meta"], {"spawn": "market"})
        self.assertNotIn("bindings", strategy)

    def test_list_strategies_preserves_insert_order_for_auto_fill_assumptions(self):
        self.write_seed(
            "mirage.json",
            {
                "mapSlug": "mirage",
                "mapName": "Mirage",
                "strategies": [
                    {
                        "side": "T",
                        "name": "First",
                        "description": "First ordered strategy.",
                        "message": "first call",
                    },
                    {
                        "side": "T",
                        "name": "Second",
                        "description": "Second ordered strategy.",
                        "message": "second call",
                    },
                    {
                        "side": "T",
                        "name": "Third",
                        "description": "Third ordered strategy.",
                        "message": "third call",
                    },
                ],
            },
        )
        app.init_db()

        with app.get_connection() as conn:
            relevant = [
                strategy
                for strategy in app.list_strategies(conn)
                if strategy["mapSlug"] == "mirage" and strategy["side"] == "T"
            ]

        self.assertEqual([strategy["name"] for strategy in relevant[:3]], ["First", "Second", "Third"])
        auto_fill_messages = [strategy["message"] for strategy in relevant[:9]]
        self.assertEqual(auto_fill_messages, ["first call", "second call", "third call"])

    def test_init_db_migrates_legacy_bindings_to_message_schema(self):
        app.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with app.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE maps (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );
                INSERT INTO maps(slug, name) VALUES ('mirage', 'Mirage');
                CREATE TABLE strategies (
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
                INSERT INTO strategies(map_slug, side, name, description, creator, source, bindings_json)
                VALUES (
                    'mirage',
                    'T',
                    'Legacy strat',
                    'Old slot-based format.',
                    'System',
                    'legacy.json',
                    '{"2": "say_team flash out", "9": "say_team save"}'
                );
                """
            )
            conn.commit()

        self.write_seed(
            "mirage.json",
            {"mapSlug": "mirage", "mapName": "Mirage", "strategies": []},
        )

        app.init_db()

        with app.get_connection() as conn:
            row = conn.execute("SELECT message, meta_json FROM strategies WHERE name = 'Legacy strat'").fetchone()
            strategies = app.list_strategies(conn)

        self.assertEqual(row["message"], "flash out")
        self.assertEqual(json.loads(row["meta_json"]), {})
        self.assertEqual(strategies[0]["message"], "flash out")


if __name__ == "__main__":
    unittest.main()
