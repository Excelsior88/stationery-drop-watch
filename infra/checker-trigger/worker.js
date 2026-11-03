// Cloudflare Worker: starts the stock checker workflow on a cron, because
// GitHub's own schedule was skipping most runs. Needs secret GITHUB_TOKEN
// (fine-grained, Excelsior88/stationery-drop-watch only, Actions: read & write).
const REPO = "Excelsior88/stationery-drop-watch";
const WORKFLOW = "check-and-deploy.yml";

async function dispatch(env) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stationerydropwatch-checker-trigger",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  return res.status; // 204 = started
}

export default {
  async scheduled(event, env, ctx) {
    const status = await dispatch(env);
    console.log(`dispatch status ${status}`);
    if (status !== 204) throw new Error(`GitHub dispatch failed: ${status}`);
  },
  async fetch() {
    return new Response("ok");
  },
};
