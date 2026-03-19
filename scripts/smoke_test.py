import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 18080
BASE_URL = f"http://127.0.0.1:{PORT}"


def fetch_json(path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def fetch_text(path):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5) as response:
        return response.status, response.read().decode("utf-8")


def wait_for_server():
    last_error = None
    for _ in range(50):
        try:
            status, payload = fetch_json("/healthz")
            if status == 200 and payload == {"status": "ok"}:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
            last_error = error
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready: {last_error}")


def main():
    temp_dir = tempfile.mkdtemp(prefix="cs2-strat-builder-")
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["DATABASE_PATH"] = str(Path(temp_dir) / "strats.db")

    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for_server()

        status, health = fetch_json("/healthz")
        assert status == 200
        assert health == {"status": "ok"}

        status, data = fetch_json("/api/data")
        assert status == 200
        assert len(data["maps"]) >= 3
        assert len(data["strategies"]) >= 4
        assert {strategy["source"] for strategy in data["strategies"]} >= {
            "ancient.json",
            "inferno.json",
            "mirage.json",
        }

        status, html = fetch_text("/")
        assert status == 200
        assert "CS2 Strat Builder" in html

        status, created = fetch_json(
            "/api/strategies",
            method="POST",
            payload={
                "creator": "Smoke Squad",
                "mapSlug": "inferno",
                "side": "CT",
                "name": "A fast rotate",
                "description": "Rotate quickly and call the crossfire.",
                "bindings": {
                    "1": "say_team smoke short",
                    "2": "say_team flash site",
                },
            },
        )
        assert status == 201
        assert created["source"] == "database"
        assert "bind KP_END" in created["command"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
