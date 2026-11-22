import { guardBash } from "./pre/kill-guard.ts";

const blocked = ['pkill -f sm.sh', 'killall foo', 'pgrep -f x', 'kill $(pgrep foo)', 'ps aux | grep x | xargs kill', 'echo hi; pkill x'];
const allowed = ['kill 123', 'pgrep -x foo', 'git status', 'echo pkillx'];
let bad = 0;
for (const c of blocked) if (!guardBash(c)) { console.log("NOT blocked:", c); bad++; }
for (const c of allowed) if (guardBash(c)) { console.log("wrongly blocked:", c); bad++; }
console.log(bad ? "FAIL" : "ok");
process.exit(bad ? 1 : 0);
