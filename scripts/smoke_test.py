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
HEALTH_PAYLOAD = {"status": "ok"}
TRANSIENT_HEALTH_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    OSError,
    ValueError,
)


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


def wait_for_json_response(url, expected_payload, attempts=50, delay_seconds=0.2, timeout=5):
    last_error = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload == expected_payload:
                    return payload
                last_error = RuntimeError(
                    f"unexpected response from {url}: {response.status} {payload}"
                )
        except TRANSIENT_HEALTH_ERRORS as error:
            last_error = error
        time.sleep(delay_seconds)

    raise RuntimeError(f"Server did not become ready at {url}: {last_error}")


def wait_for_server():
    return wait_for_json_response(
        f"{BASE_URL}/healthz",
        HEALTH_PAYLOAD,
        attempts=50,
        delay_seconds=0.2,
        timeout=5,
    )


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
        assert health == HEALTH_PAYLOAD

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
        assert "CS2 Chat Strat Builder" in html
        assert "Python" not in html
        assert "Add your own strategy" not in html

        status, created = fetch_json(
            "/api/strategies",
            method="POST",
            payload={
                "creator": "Smoke Squad",
                "mapSlug": "inferno",
                "side": "CT",
                "name": "A fast rotate",
                "description": "Rotate quickly and call the crossfire.",
                "message": "smoke short then flash site",
                "meta": {"origin": "smoke-test"},
            },
        )
        assert status == 201
        assert created["source"] == "database"
        assert created["message"] == "smoke short then flash site"
        assert created["meta"] == {"origin": "smoke-test"}
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
