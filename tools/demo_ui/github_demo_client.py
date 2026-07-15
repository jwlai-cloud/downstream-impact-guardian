"""
GitHub API client for the "trigger a real PR" demo flow.

Base URL is configurable so this exact code can run against:
  - https://api.github.com          (production)
  - http://localhost:PORT           (mock server, for testing without real creds)

All network calls go through requests.Session so auth headers are set once.
"""
import time
import uuid
import base64
from dataclasses import dataclass, field
from typing import Optional, Callable

import requests


@dataclass
class RunStatus:
    run_id: str
    step: str
    message: str
    done: bool = False
    error: Optional[str] = None


class GitHubDemoRunner:
    def __init__(self, owner: str, repo: str, token: str, base_url: str = "https://api.github.com"):
        self.owner = owner
        self.repo = repo
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/repos/{self.owner}/{self.repo}{path}"

    # ---------- individual GitHub API calls ----------

    def get_branch_sha(self, branch: str = "main") -> str:
        r = self.session.get(self._url(f"/git/ref/heads/{branch}"))
        r.raise_for_status()
        return r.json()["object"]["sha"]

    def create_branch(self, new_branch: str, from_sha: str) -> dict:
        r = self.session.post(self._url("/git/refs"), json={
            "ref": f"refs/heads/{new_branch}",
            "sha": from_sha,
        })
        r.raise_for_status()
        return r.json()

    def put_file(self, branch: str, path: str, content_str: str, message: str) -> dict:
        """Create or update a file on a branch (base64-encodes content, as the API requires)."""
        # Check if file exists on this branch to get its sha (required for updates)
        sha = None
        existing = self.session.get(self._url(f"/contents/{path}"), params={"ref": branch})
        if existing.status_code == 200:
            sha = existing.json()["sha"]

        body = {
            "message": message,
            "content": base64.b64encode(content_str.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        r = self.session.put(self._url(f"/contents/{path}"), json=body)
        r.raise_for_status()
        return r.json()

    def open_pull_request(self, head: str, base: str, title: str, body: str) -> dict:
        r = self.session.post(self._url("/pulls"), json={
            "head": head, "base": base, "title": title, "body": body,
        })
        r.raise_for_status()
        return r.json()

    def get_check_runs(self, ref: str) -> list:
        r = self.session.get(self._url(f"/commits/{ref}/check-runs"))
        r.raise_for_status()
        return r.json().get("check_runs", [])

    def get_pr_comments(self, pr_number: int) -> list:
        r = self.session.get(self._url(f"/issues/{pr_number}/comments"))
        r.raise_for_status()
        return r.json()

    def close_pull_request(self, pr_number: int) -> dict:
        r = self.session.patch(self._url(f"/pulls/{pr_number}"), json={"state": "closed"})
        r.raise_for_status()
        return r.json()

    def delete_branch(self, branch: str) -> None:
        r = self.session.delete(self._url(f"/git/refs/heads/{branch}"))
        if r.status_code not in (204, 200, 404):
            r.raise_for_status()

    # ---------- orchestration: the full demo run ----------

    def run_demo(
        self,
        template_path: str,
        template_content: str,
        base_branch: str = "main",
        poll_timeout: int = 120,
        poll_interval: int = 3,
    ):
        """
        Generator that yields RunStatus updates as it goes, so a web UI can
        stream progress live. This is the thing the Cloud Run backend calls
        per button-click.
        """
        run_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        branch_name = f"demo/run-{run_id}"
        pr_number = None

        try:
            yield RunStatus(run_id, "branch", f"Reading tip of {base_branch}...")
            base_sha = self.get_branch_sha(base_branch)

            yield RunStatus(run_id, "branch", f"Creating branch {branch_name}...")
            self.create_branch(branch_name, base_sha)

            yield RunStatus(run_id, "commit", f"Pushing breaking change to {template_path}...")
            self.put_file(
                branch_name, template_path, template_content,
                message="demo: simulate schema/logic change for Downstream Impact Guardian",
            )

            yield RunStatus(run_id, "pr", "Opening pull request...")
            pr = self.open_pull_request(
                head=branch_name, base=base_branch,
                title=f"[demo {run_id}] simulated breaking change",
                body="Automated demo run — safe to close, not intended to merge.",
            )
            pr_number = pr["number"]
            pr_ref = pr["head"]["sha"]

            yield RunStatus(run_id, "ci", f"PR #{pr_number} opened. Waiting for Actions workflow...")

            deadline = time.time() + poll_timeout
            seen_comment = False
            while time.time() < deadline:
                runs = self.get_check_runs(pr_ref)
                if runs:
                    statuses = {r["name"]: r["status"] for r in runs}
                    yield RunStatus(run_id, "ci", f"Check status: {statuses}")
                    if all(s == "completed" for s in statuses.values()):
                        break

                comments = self.get_pr_comments(pr_number)
                if comments and not seen_comment:
                    seen_comment = True
                    yield RunStatus(run_id, "comment", f"Bot commented: {comments[-1]['body'][:120]}...")
                    break

                time.sleep(poll_interval)
            else:
                # Loop exhausted without break => genuinely timed out, not success.
                yield RunStatus(run_id, "ci", "Timed out waiting for workflow.",
                                 done=True, error="timeout")
                return

            yield RunStatus(run_id, "done", f"Demo complete. See PR #{pr_number}.", done=True)

        except requests.HTTPError as e:
            yield RunStatus(run_id, "error", str(e), error=str(e), done=True)
        finally:
            # Cleanup is intentionally NOT automatic here — see cleanup_demo_run()
            pass

    def cleanup_demo_run(self, pr_number: Optional[int], branch_name: str):
        if pr_number is not None:
            try:
                self.close_pull_request(pr_number)
            except requests.HTTPError:
                pass
        try:
            self.delete_branch(branch_name)
        except requests.HTTPError:
            pass
