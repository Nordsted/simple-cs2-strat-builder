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

    def test_validate_strategy_normalizes_and_sanitizes(self):
        strategy = app.validate_strategy(
            {
                "mapSlug": " Mirage ",
                "side": " ct ",
                "name": " Retake ",
                "description": " Hold site ",
                "creator": " Team ",
                "bindings": {"2": " say_team   Flash now  ", "9": "   "},
            }
        )

        self.assertEqual(strategy["mapSlug"], "mirage")
        self.assertEqual(strategy["side"], "CT")
        self.assertEqual(strategy["creator"], "Team")
        self.assertEqual(strategy["bindings"], {"2": "Flash now"})

    def test_build_command_orders_numpad_slots(self):
        command = app.build_command({"9": "say_team last", "1": "say_team first", "5": 'say_team "mid"'})

        self.assertEqual(
            command,
            'bind KP_END "say_team first"; bind KP_5 "say_team \'mid\'"; bind KP_PGUP "say_team last"',
        )

    def test_normalize_binding_command_strips_team_chat_prefix(self):
        self.assertEqual(app.normalize_binding_command(" say_team   smoke window "), "smoke window")
        self.assertEqual(app.normalize_binding_command("flash over"), "flash over")

    def test_read_strategy_seed_rejects_invalid_payload(self):
        invalid_file = app.STRATS_DIR / "broken.json"
        invalid_file.write_text(json.dumps({"mapSlug": "mirage", "strategies": []}), encoding="utf-8")

        with self.assertRaises(ValueError):
            app.read_strategy_seed(invalid_file)

    def test_init_db_seeds_maps_and_strategies_from_files(self):
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
                        "bindings": {"1": "say_team smoke window"},
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
                        "bindings": {"2": "say_team molly banana"},
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
        self.assertEqual({strategy["source"] for strategy in strategies}, {"inferno.json", "mirage.json"})
        self.assertEqual(strategies[0]["bindings"], {"2": "molly banana"})

    def test_insert_strategy_defaults_source_to_database(self):
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
                        "bindings": {"1": "say_team smoke window"},
                    }
                ],
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
                    "bindings": {"4": "say_team group market"},
                },
            )
            conn.commit()

        self.assertEqual(strategy["source"], "database")
        self.assertIn("bind KP_LEFTARROW", strategy["command"])


if __name__ == "__main__":
    unittest.main()
