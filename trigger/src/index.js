// One cron, one command: the radar workflow's `command` input.
const COMMANDS = {
  "0 0,8,16 * * *": "sources",
  "15 9 * * *": "daily",
  "30 * * * *": "searchwords",
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

export default {
  async scheduled(event, env) {
    const command = COMMANDS[event.cron];
    if (!command) throw new Error(`no command for cron ${event.cron}`);
    const status = await dispatch(env, command);
    console.log(`${command} dispatched (${status})`);
  },
};
