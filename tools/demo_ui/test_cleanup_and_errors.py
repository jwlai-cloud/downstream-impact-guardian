import time
import subprocess
import sys

sys.path.insert(0, "/home/claude/repo-package/tools/demo_ui")
from github_demo_client import GitHubDemoRunner
import requests

MOCK_URL = "http://localhost:5056"

server = subprocess.Popen(
    [sys.executable, "-c", f"""
import sys
sys.path.insert(0, "/home/claude/repo-package/tools/demo_ui")
import mock_github_server as m
m.app.run(port=5056)
"""],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
time.sleep(1.5)

failures = []

try:
    # --- Test 1: cleanup actually closes PR and deletes branch ---
    runner = GitHubDemoRunner("testorg", "downstream-impact-guardian-demo", "fake-token-123", base_url=MOCK_URL)
    branch = "demo/run-cleanup-test"
    sha = runner.get_branch_sha("main")
    runner.create_branch(branch, sha)
    runner.put_file(branch, "models/schema.yml", "x: 1", "test commit")
    pr = runner.open_pull_request(branch, "main", "cleanup test", "body")
    pr_number = pr["number"]

    runner.cleanup_demo_run(pr_number, branch)

    # verify branch gone
    r = requests.get(f"{MOCK_URL}/repos/testorg/downstream-impact-guardian-demo/git/ref/heads/{branch}",
                      headers={"Authorization": "Bearer fake-token-123"})
    if r.status_code == 404:
        print("PASS: branch deleted after cleanup")
    else:
        failures.append(f"branch still exists after cleanup, status={r.status_code}")

    # --- Test 2: bad token surfaces as a clear error, not a silent hang ---
    bad_runner = GitHubDemoRunner("testorg", "downstream-impact-guardian-demo", "expired-or-wrong-token", base_url=MOCK_URL)
    try:
        bad_runner.get_branch_sha("main")
        failures.append("expected HTTPError on bad auth, got none")
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            print("PASS: bad auth correctly raises 401 HTTPError")
        else:
            failures.append(f"expected 401, got {e.response.status_code}")

    # --- Test 3: run_demo() surfaces errors through the generator, doesn't crash silently ---
    broken_runner = GitHubDemoRunner("testorg", "downstream-impact-guardian-demo", "expired-or-wrong-token", base_url=MOCK_URL)
    statuses = list(broken_runner.run_demo("models/schema.yml", "content", poll_timeout=3, poll_interval=1))
    last = statuses[-1]
    if last.error is not None and last.done:
        print(f"PASS: run_demo() surfaces auth failure cleanly: {last.error[:60]}...")
    else:
        failures.append(f"run_demo() did not surface the error cleanly: {statuses}")

finally:
    server.terminate()
    server.wait(timeout=5)

print()
if failures:
    print("FAILURES:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
else:
    print("ALL PASS")
