// Four runs a day, at 08:00, 12:00, 17:00 and 21:00 Beijing time: each cron starts the radar
// workflow once per command, in order (the workflow's concurrency group runs them one by one).
// searchwords every time; sources (with the heartbeat) morning and night; daily at 17:00, after
// WhoisDS publishes the day's new domains (about 08:30 UTC). No more than two a cron: GitHub
// keeps one run pending per concurrency group, and a third would cancel the second.
const COMMANDS = {
  "0 0,13 * * *": ["sources", "searchwords"],
  "0 4 * * *": ["searchwords"],
  "0 9 * * *": ["daily", "searchwords"],
};

async function dispatch(env, command) {
  const url = `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`;
  const init = {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "new-term-radar-trigger",
    },
    body: JSON.stringify({ ref: env.REF, inputs: { command } }),
  };
  // GitHub answers 204; a 5xx or a dropped connection is tried once more
  for (let attempt = 0; ; attempt++) {
    let res;
    try {
      res = await fetch(url, init);
    } catch (err) {
      if (attempt) throw err;
      continue;
    }
    if (res.ok) return res.status;
    const why = `${command}: GitHub ${res.status} ${(await res.text()).slice(0, 200)}`;
    if (attempt || res.status < 500) throw new Error(why);
  }
}

// A failed dispatch says so in Feishu, when the Worker has the radar's three Feishu secrets:
// on 24 October 2026 GitHub Actions was off for the repository and every run failed for
// fourteen hours with nothing but a missing card to show for it.
async function alert(env, text) {
  if (!env.FEISHU_APP_ID || !env.FEISHU_APP_SECRET || !env.FEISHU_RECEIVE_ID) return;
  const api = "https://open.feishu.cn/open-apis";
  const json = { "Content-Type": "application/json; charset=utf-8" };
  const auth = await (await fetch(`${api}/auth/v3/tenant_access_token/internal`, {
    method: "POST", headers: json,
    body: JSON.stringify({ app_id: env.FEISHU_APP_ID, app_secret: env.FEISHU_APP_SECRET }),
  })).json();
  await fetch(`${api}/im/v1/messages?receive_id_type=${env.FEISHU_RECEIVE_ID_TYPE || "chat_id"}`, {
    method: "POST", headers: { ...json, Authorization: `Bearer ${auth.tenant_access_token}` },
    body: JSON.stringify({ receive_id: env.FEISHU_RECEIVE_ID, msg_type: "text", content: JSON.stringify({ text }) }),
  });
}

export default {
  async scheduled(event, env) {
    const commands = COMMANDS[event.cron];
    if (!commands) throw new Error(`no command for cron ${event.cron}`);
    for (const command of commands) {
      let status;
      try {
        status = await dispatch(env, command);
      } catch (err) {
        await alert(env, `新词雷达没能启动 ${command}：${err.message}`).catch(() => {});
        throw err;
      }
      console.log(`${command} dispatched (${status})`);
    }
  },
};
