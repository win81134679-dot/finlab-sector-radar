// app/api/trigger-analysis/route.ts
// Vercel Cron Job endpoint — 每天 UTC 12:30 觸發 GitHub Actions workflow_dispatch
// Vercel 自動注入 Authorization: Bearer ${CRON_SECRET} 到 cron 請求中
export const runtime = "edge";

export async function GET(request: Request) {
  // 驗證 Vercel Cron 的 Authorization header
  const authHeader = request.headers.get("authorization");
  const expectedToken = process.env.CRON_SECRET;
  if (!expectedToken || authHeader !== `Bearer ${expectedToken}`) {
    return new Response("Unauthorized", { status: 401 });
  }

  const repo  = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;

  if (!repo || !token) {
    return new Response("Missing GITHUB_REPO or GITHUB_DISPATCH_TOKEN env vars", {
      status: 500,
    });
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/daily_analysis.yml/dispatches`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Accept":        "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type":  "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });

  if (res.ok || res.status === 204) {
    return new Response(
      JSON.stringify({ ok: true, triggered_at: new Date().toISOString() }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  const errText = await res.text().catch(() => "");
  return new Response(
    JSON.stringify({ ok: false, status: res.status, error: errText }),
    { status: 500, headers: { "Content-Type": "application/json" } }
  );
}
