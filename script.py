import sys
import subprocess
import stat
import json
from pathlib import Path
import os
import shutil

with open("config.json", "r") as f:
    CONFIG = json.load(f)


def run(cmd, cwd=None, capture=False):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=capture, text=True)
    return result


def delete_tracker_folder_locally():
    tracker_path = Path(CONFIG["tracker_local_path"])

    if not tracker_path.exists():
        print("No local tracker repo found, skipping.")
        return

    print(f"Clearing tracker folder at: {tracker_path}")

    def force_remove(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    for item in tracker_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item, onerror=force_remove)
        else:
            try:
                item.unlink()
            except PermissionError:
                os.chmod(item, stat.S_IWRITE)
                item.unlink()

    print("✅ Tracker folder cleared (folder kept, all files deleted).")


def create_github_repo():
    print("Creating commit-tracker repo on GitHub...")

    check = run("gh --version", capture=True)
    if check.returncode != 0:
        print("GitHub CLI not installed — create repo manually at github.com")
        return False

    result = run("gh repo create commit-tracker --public", capture=True)

    if result.returncode == 0:
        print("✅ Repo created successfully!")
        return True
    elif (
        "Name already exists" in result.stderr
        or "already exists" in result.stderr.lower()
    ):
        print("✅ Repo already exists on GitHub — continuing to clone...")
        return True
    else:
        print(f"❌ Failed to create repo on GitHub: {result.stderr}")
        return False


def setup_ssh_config():
    print(1, "Configure SSH for Multiple GitHub Accounts")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    config_path = ssh_dir / "config"

    existing = config_path.read_text() if config_path.exists() else ""

    new_blocks = []

    main_block = f"""
Host {CONFIG["ssh_host_alias"]}
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_{CONFIG["ssh_host_alias"].replace("github-", "")}
"""
    if CONFIG["ssh_host_alias"] not in existing:
        new_blocks.append(main_block)
        print(f"Will add SSH block for: {CONFIG['ssh_host_alias']}")
    else:
        print(f"SSH block already exists for: {CONFIG['ssh_host_alias']}")

    for acct in CONFIG["extra_accounts"]:
        block = f"""
Host {acct["alias"]}
  HostName github.com
  User git
  IdentityFile {acct["key_file"]}
  # {acct["comment"]}
"""
        if acct["alias"] not in existing:
            new_blocks.append(block)
            print(f"Will add SSH block for: {acct['alias']} ({acct['comment']})")
        else:
            print(f"SSH block already exists for: {acct['alias']}")

    if new_blocks:
        with open(config_path, "a") as f:
            f.write("\n# Added by setup_commit_tracker.py\n")
            for block in new_blocks:
                f.write(block)
        config_path.chmod(0o600)
        print("SSH config updated.")

    print("Generate SSH keys if you haven't already:")
    print(f"""
    # For main account:
    ssh-keygen -t ed25519 -C "{CONFIG["main_email"]}" -f ~/.ssh/id_{CONFIG["ssh_host_alias"].replace("github-", "")}

    # For each extra account:
    ssh-keygen -t ed25519 -C "work@email.com" -f ~/.ssh/id_work

    # Then add the PUBLIC key (.pub) to each GitHub account:
    # GitHub → Settings → SSH and GPG Keys → New SSH Key
    cat ~/.ssh/id_{CONFIG["ssh_host_alias"].replace("github-", "")}.pub
    """)


def setup_tracker_repo():
    print(2, "Set Up Local Tracker Repo")

    tracker_path = Path(CONFIG["tracker_local_path"]).expanduser().resolve()

    res = create_github_repo()

    if not res:
        print("Failed to create repo on GitHub")
        return

    if os.path.exists(tracker_path):
        delete_tracker_folder_locally()
    else:
        tracker_path.mkdir(parents=True, exist_ok=True)

    print(f"Cloning tracker repo to: {tracker_path}")
    result = run(f"git clone {CONFIG['tracker_repo_url']} {tracker_path}")

    if result.returncode != 0:
        print("Clone failed")
    else:
        print("Tracker repo cloned successfully.")


def write_post_commit_hook():
    print(3, "Write Global Post-Commit Hook")

    hooks_dir = Path.home() / ".git-hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "post-commit"

    with open("hook.py", "r", encoding="utf-8") as f:
        hook_content = f.read()

    hook_path.write_text(hook_content, encoding="utf-8")
    hook_path.chmod(
        hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )
    print(f"Hook written to: {hook_path}")


def register_global_hook():
    print(4, "Register Hook with Global Git Config")

    hooks_dir = str(Path.home() / ".git-hooks")
    result = run(f'git config --global core.hooksPath "{hooks_dir}"')

    if result.returncode == 0:
        print(f"Global hooksPath set to: {hooks_dir}")
        print("This hook will fire for every repo on this machine automatically.")
    else:
        print("Could not set global hooksPath. Run manually:")
        print(f'    git config --global core.hooksPath "{hooks_dir}"')


# ─────────────────────────────────────────────
# STEP 5 — Backfill Past Commits (Optional)
# ─────────────────────────────────────────────

# def backfill_commits(repo_path: str):
#     """
#     Call this function manually to backfill old commits from any repo.
#     Example: backfill_commits("/path/to/old/private/repo")
#     """
#     print("5 (optional)", f"Backfill Past Commits from: {repo_path}")

#     if not Path(repo_path).exists():
#         print(f"Repo not found: {repo_path}")
#         return

#     result = run(
#         'git log --pretty=format:"%ci|||%s" --reverse',
#         cwd=repo_path, capture=True
#     )
#     # result here uses capture=True alias — fix:
#     r = subprocess.run(
#         'git log --pretty=format:"%ci|||%s" --reverse',
#         shell=True, cwd=repo_path, capture_output=True, text=True
#     )

#     lines = r.stdout.strip().split("\n")
#     repo_name = Path(repo_path).name
#     tracker = Path(CONFIG["tracker_local_path"])
#     log_file = tracker / "activity.log"

#     print(f"Replaying {len(lines)} commits from {repo_name}...")

#     for line in lines:
#         if "|||" not in line:
#             continue
#         date_str, msg = line.split("|||", 1)
#         date_str = date_str.strip()
#         msg = msg.strip()[:80]

#         log_entry = f"[{date_str}] [{repo_name}] [backfill] {msg}\n"
#         with open(log_file, "a") as f:
#             f.write(log_entry)

#         env = os.environ.copy()
#         env["GIT_AUTHOR_NAME"]      = CONFIG["main_name"]
#         env["GIT_AUTHOR_EMAIL"]     = CONFIG["main_email"]
#         env["GIT_COMMITTER_NAME"]   = CONFIG["main_name"]
#         env["GIT_COMMITTER_EMAIL"]  = CONFIG["main_email"]
#         env["GIT_AUTHOR_DATE"]      = date_str
#         env["GIT_COMMITTER_DATE"]   = date_str

#         subprocess.run("git add activity.log", shell=True, cwd=str(tracker), env=env)
#         subprocess.run(
#             f'git commit -m "backfill: [{repo_name}] {msg}"',
#             shell=True, cwd=str(tracker), env=env
#         )

#     subprocess.run("git push origin main", shell=True, cwd=str(tracker))
#     print(f"Backfill complete. {len(lines)} commits pushed.")


def main():
    print("\n🚀  Git Commit Tracker — Setup Script")

    if "your-main@email.com" in CONFIG["main_email"]:
        print("Please edit the CONFIG section at the top of this script first!")
        print("Set your real name, email, GitHub username, and tracker repo URL.")
        sys.exit(1)

    setup_ssh_config()
    setup_tracker_repo()
    write_post_commit_hook()
    register_global_hook()
    print("\n🚀  Git Commit Tracker — Setup Complete")


if __name__ == "__main__":
    main()
