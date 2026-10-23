"""
management/git_sync.py
DevOps & cPanel Git Live Synchronization Engine for U-Connect.
Handles change detection, commit comparisons, one-click automated pulling,
migrations, static asset collection, and cPanel Phusion Passenger restarts.
"""

import logging
import os
import subprocess
import sys
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

GIT_STATUS_CACHE_KEY = "uc_git_sync_status_cache"
GIT_STATUS_CACHE_TIMEOUT = 120  # Cache for 2 minutes to prevent hammering remote


def _run_cmd(cmd_list, timeout=25):
    """Safely executes a shell or git command within BASE_DIR and returns output."""
    try:
        p = subprocess.run(
            cmd_list,
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": p.returncode == 0,
            "stdout": (p.stdout or "").strip(),
            "stderr": (p.stderr or "").strip(),
            "returncode": p.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }


def get_git_status(force_refresh=False):
    """
    Checks the local git commit vs the remote GitHub repository.
    Returns whether there are changes waiting to be pulled to cPanel.
    """
    if not force_refresh:
        cached = cache.get(GIT_STATUS_CACHE_KEY)
        if cached:
            return cached

    # 1. Determine current active branch
    branch_res = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    branch = branch_res["stdout"] if branch_res["success"] else "main"
    if not branch or branch == "HEAD":
        branch = "main"

    # 2. Local commit details
    local_hash_res = _run_cmd(["git", "rev-parse", "HEAD"], timeout=5)
    local_full = local_hash_res["stdout"] if local_hash_res["success"] else ""
    local_short = local_full[:7] if local_full else "unknown"

    log_res = _run_cmd(["git", "log", "-1", "--pretty=format:%s|||%an|||%cr"], timeout=5)
    local_subject = "No commits found"
    local_author = "Unknown"
    local_time = ""
    if log_res["success"] and "|||" in log_res["stdout"]:
        parts = log_res["stdout"].split("|||")
        if len(parts) >= 3:
            local_subject = parts[0]
            local_author = parts[1]
            local_time = parts[2]

    # 3. Check remote commit via git ls-remote (fast, doesn't modify working tree)
    remote_full = ""
    remote_short = ""
    remote_res = _run_cmd(["git", "ls-remote", "origin", f"refs/heads/{branch}"], timeout=10)
    if remote_res["success"] and remote_res["stdout"]:
        first_line = remote_res["stdout"].splitlines()[0]
        remote_full = first_line.split()[0].strip()
        remote_short = remote_full[:7]

    # 4. Count commits behind / ahead
    ahead = 0
    behind = 0
    if remote_full and local_full:
        # Fetch remote reference quietly to calculate rev-list accurately
        _run_cmd(["git", "fetch", "origin", branch, "--quiet"], timeout=12)
        count_res = _run_cmd(["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"], timeout=8)
        if count_res["success"] and count_res["stdout"]:
            try:
                parts = count_res["stdout"].split()
                if len(parts) >= 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
            except (ValueError, IndexError):
                pass

    # A server has pending changes to pull if:
    # 1. 'behind' count > 0, OR
    # 2. Remote commit exists and is different from local commit (and behind isn't calculated yet)
    has_changes = (behind > 0) or bool(remote_full and local_full and remote_full != local_full and ahead == 0)

    result = {
        "status": "success",
        "branch": branch,
        "local_commit": local_short,
        "local_full_hash": local_full,
        "local_subject": local_subject,
        "local_author": local_author,
        "local_time": local_time,
        "remote_commit": remote_short,
        "remote_full_hash": remote_full,
        "ahead": ahead,
        "behind": behind,
        "has_changes": has_changes,
        "is_up_to_date": not has_changes and bool(local_full),
        "last_checked": timezone.now().strftime("%H:%M:%S"),
    }

    cache.set(GIT_STATUS_CACHE_KEY, result, GIT_STATUS_CACHE_TIMEOUT)
    return result


def perform_git_sync(user=None):
    """
    Executes the automated synchronization agent:
    1. git fetch origin <branch>
    2. git reset --hard origin/<branch>
    3. python manage.py migrate --noinput
    4. python manage.py collectstatic --noinput
    5. python manage.py compilemessages (if available)
    6. touch tmp/restart.txt (reloads cPanel Passenger)
    """
    steps_log = []
    overall_success = True
    start_time = datetime.now()

    # Determine branch
    branch_res = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    branch = branch_res["stdout"] if branch_res["success"] else "main"
    if not branch or branch == "HEAD":
        branch = "main"

    python_bin = sys.executable or "python3"
    manage_py = os.path.join(settings.BASE_DIR, "manage.py")

    # Step 1: Git Fetch
    fetch_res = _run_cmd(["git", "fetch", "origin", branch], timeout=30)
    steps_log.append({
        "step": "1. Git Fetch",
        "command": f"git fetch origin {branch}",
        "success": fetch_res["success"],
        "output": fetch_res["stdout"] or fetch_res["stderr"] or "Fetched successfully.",
    })
    if not fetch_res["success"]:
        overall_success = False

    # Step 2: Git Reset / Pull
    if overall_success:
        reset_res = _run_cmd(["git", "reset", "--hard", f"origin/{branch}"], timeout=30)
        steps_log.append({
            "step": "2. Git Pull & Reset",
            "command": f"git reset --hard origin/{branch}",
            "success": reset_res["success"],
            "output": reset_res["stdout"] or reset_res["stderr"] or "Updated working tree to latest commit.",
        })
        if not reset_res["success"]:
            overall_success = False

    # Step 3: Database Migrations
    if overall_success:
        mig_res = _run_cmd([python_bin, manage_py, "migrate", "--noinput"], timeout=60)
        steps_log.append({
            "step": "3. Database Migrations",
            "command": "python manage.py migrate --noinput",
            "success": mig_res["success"],
            "output": mig_res["stdout"] or mig_res["stderr"] or "No new migrations applied.",
        })
        if not mig_res["success"]:
            overall_success = False

    # Step 4: Collect Static Assets
    if overall_success:
        stat_res = _run_cmd([python_bin, manage_py, "collectstatic", "--noinput"], timeout=60)
        steps_log.append({
            "step": "4. Collect Static Assets",
            "command": "python manage.py collectstatic --noinput",
            "success": stat_res["success"],
            "output": stat_res["stdout"] or stat_res["stderr"] or "Static files collected.",
        })

    # Step 5: Compile Translations (Optional / Non-blocking)
    if overall_success:
        msg_res = _run_cmd([python_bin, manage_py, "compilemessages", "-l", "sw", "-l", "ar"], timeout=30)
        steps_log.append({
            "step": "5. Compile Messages",
            "command": "python manage.py compilemessages",
            "success": msg_res["success"],
            "output": msg_res["stdout"] or msg_res["stderr"] or "Translations compiled.",
        })

    # Step 6: cPanel Passenger Reload (touch tmp/restart.txt)
    restart_ok = False
    restart_output = ""
    try:
        tmp_dir = os.path.join(settings.BASE_DIR, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        restart_file = os.path.join(tmp_dir, "restart.txt")
        with open(restart_file, "a"):
            os.utime(restart_file, None)
        restart_ok = True
        restart_output = f"Successfully touched {restart_file}. cPanel Phusion Passenger reload triggered."
    except Exception as e:
        restart_output = f"Warning: Could not touch restart.txt: {e}"

    steps_log.append({
        "step": "6. Restart cPanel Server",
        "command": "touch tmp/restart.txt",
        "success": restart_ok,
        "output": restart_output,
    })

    # Post-sync verification
    new_hash_res = _run_cmd(["git", "rev-parse", "--short", "HEAD"], timeout=5)
    new_hash = new_hash_res["stdout"] if new_hash_res["success"] else "updated"

    # Invalidate cache so UI immediately refreshes
    cache.delete(GIT_STATUS_CACHE_KEY)
    fresh_status = get_git_status(force_refresh=True)

    duration = round((datetime.now() - start_time).total_seconds(), 2)

    return {
        "success": overall_success,
        "duration_seconds": duration,
        "new_commit": new_hash,
        "steps": steps_log,
        "fresh_status": fresh_status,
        "message": "cPanel synchronization completed successfully!" if overall_success else "Synchronization finished with warnings or errors.",
    }
