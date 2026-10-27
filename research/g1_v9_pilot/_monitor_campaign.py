"""Monitor the novel grammar campaign run until completion (45 min cap)."""

import json
import os
import time
import urllib.request

RUN_ID = 40353504941
DEADLINE = time.monotonic() + 45 * 60


def _get(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN missing", flush=True)
        return 2
    while time.monotonic() < DEADLINE:
        try:
            run = _get(
                f"https://api.github.com/repos/ElephantRock/Resonance-World/"
                f"actions/runs/{RUN_ID}", token
            )
            print(f"run: {run['status']}/{run['conclusion']}", flush=True)
            if run["status"] == "completed":
                jobs = _get(run["jobs_url"], token)
                for job in jobs["jobs"]:
                    print(
                        f"  {job['name'][:28]} = {job['status']}/"
                        f"{job['conclusion']}",
                        flush=True,
                    )
                return 0 if run["conclusion"] == "success" else 1
        except Exception as error:  # transient API hiccups
            print(f"poll error: {type(error).__name__}: {error}", flush=True)
        time.sleep(60)
    print("MONITOR TIMEOUT", flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
