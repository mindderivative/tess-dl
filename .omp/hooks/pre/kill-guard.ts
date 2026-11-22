/**
 * Before a bash call: never signal a process by name or pattern. `pkill -f sm.sh` once killed the owner's plasmashell.
 * omp's bash tool has in-process pkill/pgrep/killall builtins that run before PATH, so a wrapper on PATH does not cover them; this hook does.
 * A throw in a `tool_call` handler blocks the tool, so the check is a pure regex test.
 */

import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export const KILL_BLOCKED = "Blocked: never signal a process by name or pattern (pkill, killall, pgrep -f, kill $(pgrep ...), ps | grep | xargs kill): `pkill -f sm.sh` once killed the owner's plasmashell. Signal only a PID you started yourself.";
/** `pkill`, `killall`, `pgrep -f` (any flag cluster with f), or a `kill` / `xargs kill` fed by pgrep, pidof or a grep, as a command word. */
const KILL_BY_PATTERN = /(?:^|[\s;&|(`$])(?:pkill|killall)\b|(?:^|[\s;&|(`$])pgrep\s+(?:-\S*f\S*|--full)\b|\bkill\b[^;&|\n]*\$\(\s*(?:pgrep|pidof)\b|\b(?:pgrep|pidof)\b[^\n]*\|\s*xargs\b[^\n]*\bkill\b|\bps\b[^\n]*\|\s*grep\b[^\n]*\|\s*(?:awk\b[^|\n]*\|\s*)?xargs\b[^\n]*\bkill\b/;

export function guardBash(command: string): { block: true; reason: string } | undefined {
	return KILL_BY_PATTERN.test(command) ? { block: true, reason: KILL_BLOCKED } : undefined;
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event: any) => {
		if (event.toolName !== "bash") return undefined;
		return guardBash(String(event.input?.command ?? ""));
	});
}
