// GET ?pr=<number>&branch=<ref> -> check-run states + the guardian comment.
const OWNER = process.env.GH_OWNER || "jwlai-cloud";
const REPO = process.env.GH_REPO || "fiction-retail-dbt";
const MARKER = "downstream-impact-guardian";

async function gh(path) {
  const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
    headers: {
      Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) throw new Error(`GitHub ${path} -> ${res.status}`);
  return res.json();
}

export default async function handler(req, res) {
  const pr = parseInt(req.query.pr, 10);
  const branch = String(req.query.branch || "");
  if (!pr || !/^demo\/run-[a-z0-9-]+$/.test(branch)) {
    return res.status(400).json({ error: "pr and branch required" });
  }
  try {
    const [checks, comments, runs] = await Promise.all([
      gh(`/commits/${encodeURIComponent(branch)}/check-runs`),
      gh(`/issues/${pr}/comments?per_page=50`),
      // The agent takes ~2-3 min, so the page needs something truthful to show
      // in the meantime. The workflow's own step states are that something --
      // real progress reported by the runner, not a guessed animation.
      gh(`/actions/runs?branch=${encodeURIComponent(branch)}&per_page=1`).catch(() => null),
    ]);

    let step = null;
    const runId = runs && runs.workflow_runs && runs.workflow_runs[0] && runs.workflow_runs[0].id;
    if (runId) {
      const jobs = await gh(`/actions/runs/${runId}/jobs`).catch(() => null);
      const job = jobs && jobs.jobs && jobs.jobs[0];
      if (job && Array.isArray(job.steps) && job.steps.length) {
        const steps = job.steps;
        const active = steps.find((s) => s.status === "in_progress");
        const done = steps.filter((s) => s.status === "completed").length;
        const failed = steps.find((s) => s.conclusion === "failure");
        step = {
          name: (failed || active || steps[steps.length - 1]).name,
          done,
          total: steps.length,
          failed: Boolean(failed),
        };
      }
    }
    // Author check is load-bearing: anyone can comment on a public PR with
    // the marker string — only the Action's own comment may be rendered.
    const guardian = (comments || []).find(
      (c) => c.user && c.user.login === "github-actions[bot]" &&
             (c.body || "").includes(MARKER));
    return res.status(200).json({
      checks: (checks.check_runs || []).map((c) => ({
        name: c.name,
        status: c.status,           // queued | in_progress | completed
        conclusion: c.conclusion,   // success | failure | null
        url: c.html_url,
      })),
      step,
      comment: guardian ? guardian.body : null,
      commentUrl: guardian ? guardian.html_url : null,
    });
  } catch (e) {
    console.error(e);
    return res.status(502).json({ error: "GitHub call failed" });
  }
}
