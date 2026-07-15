import time
import subprocess
import sys

sys.path.insert(0, "/home/claude/repo-package/tools/demo_ui")
from github_demo_client import GitHubDemoRunner

MOCK_URL = "http://localhost:5055"

# Start the mock server as a subprocess
server = subprocess.Popen(
    [sys.executable, "/home/claude/repo-package/tools/demo_ui/mock_github_server.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
time.sleep(1.5)  # let flask boot

try:
    runner = GitHubDemoRunner(owner="testorg", repo="downstream-impact-guardian-demo", token="fake-token-123", base_url=MOCK_URL)

    template_content = """models:
  - name: orders
    columns:
      - name: first_name
      - name: last_name
    # (was: customer_name, single field) — simulated breaking change
"""

    print("=== Running full demo flow against mock GitHub API ===\n")
    final_status = None
    for status in runner.run_demo(
        template_path="models/schema.yml",
        template_content=template_content,
        poll_timeout=15,
        poll_interval=1,
    ):
        print(f"[{status.step:8s}] {status.message}")
        if status.error:
            print(f"           ERROR: {status.error}")
        final_status = status

    print()
    assert final_status is not None, "no status yielded at all"
    assert final_status.done, "flow never reached done=True"
    assert final_status.error is None, f"flow ended in error: {final_status.error}"
    print("PASS: full flow completed without error, comment was detected.")

finally:
    server.terminate()
    server.wait(timeout=5)
    out = server.stdout.read().decode(errors="replace")
    if "Traceback" in out:
        print("\n--- mock server had errors ---")
        print(out)
