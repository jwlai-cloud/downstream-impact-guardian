"""
Minimal mock of the GitHub REST API endpoints GitHubDemoRunner calls.
Just enough behavior to exercise real branch/PR/polling logic end-to-end,
including a simulated CI delay and a simulated bot comment landing later.
"""
import time
import base64
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory fake repo state
state = {
    "branches": {"main": "sha-main-0001"},
    "files": {},          # (branch, path) -> content
    "prs": {},             # number -> {head, base, sha, comments: []}
    "next_pr_number": 1,
    "check_runs": {},      # sha -> [{"name":..., "status":...}]
}
lock = threading.Lock()


VALID_TOKEN = "fake-token-123"

def require_auth():
    auth = request.headers.get("Authorization", "")
    token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
    if token != VALID_TOKEN:
        return jsonify({"message": "Bad credentials"}), 401
    return None


@app.before_request
def check_auth():
    err = require_auth()
    if err:
        return err


@app.route("/repos/<owner>/<repo>/git/ref/heads/<branch>")
def get_ref(owner, repo, branch):
    with lock:
        if branch not in state["branches"]:
            return jsonify({"message": "Not Found"}), 404
        return jsonify({"object": {"sha": state["branches"][branch]}})


@app.route("/repos/<owner>/<repo>/git/refs", methods=["POST"])
def create_ref(owner, repo):
    body = request.json
    ref = body["ref"]  # "refs/heads/xyz"
    branch = ref.split("refs/heads/")[1]
    with lock:
        state["branches"][branch] = body["sha"]
    return jsonify({"ref": ref, "object": {"sha": body["sha"]}}), 201


@app.route("/repos/<owner>/<repo>/git/refs/heads/<branch>", methods=["DELETE"])
def delete_ref(owner, repo, branch):
    with lock:
        state["branches"].pop(branch, None)
    return "", 204


@app.route("/repos/<owner>/<repo>/contents/<path:path>", methods=["GET", "PUT"])
def contents(owner, repo, path):
    if request.method == "GET":
        branch = request.args.get("ref", "main")
        with lock:
            existing = state["files"].get((branch, path))
        if existing is None:
            return jsonify({"message": "Not Found"}), 404
        return jsonify({"sha": "filesha-" + str(hash(existing))[:8]})

    body = request.json
    branch = body["branch"]
    content = base64.b64decode(body["content"]).decode()
    with lock:
        state["files"][(branch, path)] = content
        new_sha = "sha-" + uuid_like()
        state["branches"][branch] = new_sha
        # Simulate a CI workflow kicking off on this commit, completing after a short delay
        state["check_runs"][new_sha] = [{"name": "downstream-impact-guardian", "status": "in_progress"}]

    def finish_ci():
        time.sleep(4)  # simulate the Action actually running dbt + agent logic
        with lock:
            state["check_runs"][new_sha] = [{"name": "downstream-impact-guardian", "status": "completed"}]
            # simulate the bot posting its PR comment right as CI finishes
            for pr in state["prs"].values():
                if pr["sha"] == new_sha:
                    pr["comments"].append({
                        "body": "Schema change detected: `customer_name` split into `first_name`/`last_name`. "
                                "3 downstream consumers found via DataHub lineage. Proposed compatibility view attached."
                    })

    threading.Thread(target=finish_ci, daemon=True).start()
    return jsonify({"content": {"sha": "filesha-new"}}), 201


@app.route("/repos/<owner>/<repo>/pulls", methods=["POST"])
def open_pr(owner, repo):
    body = request.json
    with lock:
        n = state["next_pr_number"]
        state["next_pr_number"] += 1
        head_sha = state["branches"][body["head"]]
        state["prs"][n] = {
            "number": n, "head": body["head"], "base": body["base"],
            "sha": head_sha, "comments": [],
        }
    return jsonify({"number": n, "head": {"sha": head_sha}}), 201


@app.route("/repos/<owner>/<repo>/pulls/<int:number>", methods=["PATCH"])
def patch_pr(owner, repo, number):
    with lock:
        if number in state["prs"]:
            state["prs"][number]["state"] = request.json.get("state")
    return jsonify({"number": number, "state": "closed"})


@app.route("/repos/<owner>/<repo>/commits/<sha>/check-runs")
def check_runs(owner, repo, sha):
    with lock:
        runs = state["check_runs"].get(sha, [])
    return jsonify({"check_runs": runs})


@app.route("/repos/<owner>/<repo>/issues/<int:number>/comments")
def get_comments(owner, repo, number):
    with lock:
        pr = state["prs"].get(number)
    return jsonify(pr["comments"] if pr else [])


_counter = [0]
def uuid_like():
    _counter[0] += 1
    return f"{_counter[0]:06d}"


if __name__ == "__main__":
    app.run(port=5055)
