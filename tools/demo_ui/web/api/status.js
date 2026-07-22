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
    const [checks, comments] = await Promise.all([
      gh(`/commits/${encodeURIComponent(branch)}/check-runs`),
      gh(`/issues/${pr}/comments?per_page=50`),
    ]);
    const guardian = (comments || []).find((c) => (c.body || "").includes(MARKER));
    return res.status(200).json({
      checks: (checks.check_runs || []).map((c) => ({
        name: c.name,
        status: c.status,           // queued | in_progress | completed
        conclusion: c.conclusion,   // success | failure | null
        url: c.html_url,
      })),
      comment: guardian ? guardian.body : null,
      commentUrl: guardian ? guardian.html_url : null,
    });
  } catch (e) {
    console.error(e);
    return res.status(502).json({ error: "GitHub call failed" });
  }
}
