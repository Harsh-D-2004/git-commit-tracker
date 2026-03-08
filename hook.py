import os
import sys
import subprocess
from pathlib import Path
import json

with open("config.json", "r") as f:
    CONFIG = json.load(f)

TRACKER_PATH = f"{CONFIG['tracker_local_path']}"
MAIN_NAME = f"{CONFIG['main_name']}"
MAIN_EMAIL = f"{CONFIG['main_email']}"


def run(cmd, cwd=None, env=None):
    return subprocess.run(
        cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True
    )


def get_git(cmd, cwd=None):
    r = run(f"git {cmd}", cwd=cwd)
    return r.stdout.strip()


def main():

    repo_root = get_git("rev-parse --show-toplevel")
    repo_name = Path(repo_root).name
    commit_hash = get_git("rev-parse HEAD")
    commit_msg = get_git("log -1 --pretty=%B")
    commit_date = get_git("log -1 --pretty=%ci")
    branch = get_git("rev-parse --abbrev-ref HEAD")

    if Path(repo_root).resolve() == Path(TRACKER_PATH).resolve():
        sys.exit(0)

    log_line = (
        f"[{commit_date}] "
        f"[{repo_name}] "
        f"[{branch}] "
        f"{commit_hash[:8]} — {commit_msg.strip()[:80]}\n"
    )

    tracker = Path(TRACKER_PATH)
    if not tracker.exists():
        print(f"[tracker] ⚠️  Tracker repo not found at {TRACKER_PATH}, skipping.")
        sys.exit(0)

    log_file = tracker / "activity.log"
    if not log_file.exists():
        log_file.touch(mode=0o644)
    with open(log_file, "a") as f:
        f.write(log_line)

    # Set env so this commit is attributed to the MAIN account
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = MAIN_NAME
    env["GIT_AUTHOR_EMAIL"] = MAIN_EMAIL
    env["GIT_COMMITTER_NAME"] = MAIN_NAME
    env["GIT_COMMITTER_EMAIL"] = MAIN_EMAIL
    env["GIT_AUTHOR_DATE"] = commit_date
    env["GIT_COMMITTER_DATE"] = commit_date

    run("git add activity.log", cwd=TRACKER_PATH, env=env)
    run(
        f'git commit -m "activity: [{repo_name}] {commit_msg.strip()[:60]}"',
        cwd=TRACKER_PATH,
        env=env,
    )
    result = run("git push origin main", cwd=TRACKER_PATH, env=env)

    if result.returncode == 0:
        print("[tracker] ✅  Activity logged and pushed.")
    else:
        print("[tracker] ⚠️  Push failed — will retry next commit.")
        print(result.stderr[:200])


if __name__ == "__main__":
    main()
