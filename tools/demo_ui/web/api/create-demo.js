// POST {scenario: "rename" | "delete"} -> creates a unique demo branch from
// the pre-staged scenario branch and opens a PR in the consumer repo.
// Token is a fine-grained PAT scoped to ONE demo repo, server-side only.
const SCENARIOS = {
  rename: {
    branch: "demo/rename-order-total",
    title: "Standardize order amounts to USD and redefine gross revenue",
  },
  delete: {
    branch: "demo/delete-revenue-daily",
    title: "Remove revenue_daily — finance says they don't use it anymore",
  },
};
const MAX_OPEN_RUNS = 5;
const STALE_MINUTES = 45;

const OWNER = process.env.GH_OWNER || "jwlai-cloud";
const REPO = process.env.GH_REPO || "fiction-retail-dbt";

async function gh(path, opts = {}) {
  const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
    ...opts,
    headers: {
      Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`GitHub ${path} -> ${res.status}: ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

async function cleanupStale() {
  const prs = await gh(`/pulls?state=open&per_page=50`);
  const runs = prs.filter((p) => p.head.ref.startsWith("demo/run-"));
  const cutoff = Date.now() - STALE_MINUTES * 60 * 1000;
  for (const p of runs) {
    if (new Date(p.created_at).getTime() < cutoff) {
      await gh(`/pulls/${p.number}`, { method: "PATCH", body: JSON.stringify({ state: "closed" }) });
      await gh(`/git/refs/heads/${p.head.ref}`, { method: "DELETE" }).catch(() => {});
    }
  }
  return runs.filter((p) => new Date(p.created_at).getTime() >= cutoff).length;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const scenario = SCENARIOS[(req.body || {}).scenario];
  if (!scenario) return res.status(400).json({ error: "scenario must be 'rename' or 'delete'" });

  try {
    const active = await cleanupStale();
    if (active >= MAX_OPEN_RUNS) {
      return res.status(429).json({ error: "Too many demo runs in flight — try again in a few minutes." });
    }
    const src = await gh(`/git/ref/heads/${encodeURIComponent(scenario.branch)}`);
    const branch = `demo/run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    await gh(`/git/refs`, {
      method: "POST",
      body: JSON.stringify({ ref: `refs/heads/${branch}`, sha: src.object.sha }),
    });
    const pr = await gh(`/pulls`, {
      method: "POST",
      body: JSON.stringify({
        base: "main",
        head: branch,
        title: scenario.title,
        body:
          "Opened by the [Downstream Impact Guardian demo](https://github.com/jwlai-cloud/downstream-impact-guardian) " +
          "— a fresh copy of a staged breaking change. The guardian's report lands below in ~60s. " +
          "Auto-closed after " + STALE_MINUTES + " minutes.",
      }),
    });
    return res.status(200).json({ number: pr.number, url: pr.html_url, branch });
  } catch (e) {
    console.error(e);
    return res.status(502).json({ error: "GitHub call failed — try again shortly." });
  }
}
