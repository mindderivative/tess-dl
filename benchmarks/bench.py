"""Timing and memory of the `tdl` reader against the budget (docs/api.md, "Performance Budget").

Standard library only; not shipped, and nothing under `src/` imports it.

    ~/Projects/pyDev/pyEnvs/tess-dl/bin/python benchmarks/bench.py [--runs N]

Reports, for each input: size, best-of-N time for `loads`, `parse`, `dumps` and one
`with_metadata`, and the memory the tree keeps (`tracemalloc`). Then the scaling check
(1x, 2x, 4x input) and the adversarial inputs. Exit status is 1 if the budget is missed.
"""

import argparse
import gc
import platform
import sys
import time
import tracemalloc

import tdl

BUDGET_100K = 0.020  # seconds for a 100 KB file
BUDGET_1M = 0.250  # seconds for a file at the 1 MiB limit
SIZES = (250_000, 500_000, 1_000_000)
HEAD = "---\nTDL: 0.1\nName: Bench_Root\nShell: 0.1\nUID: 0192d3c4-7a1e-7c2f\n---\n"

MONITOR = """\
  # one monitor
  Monitor {{
    Name: Monitor_{i}
    Connector: DP-{i}
    Bar {{
      Name: Bar_{i}
      Edge: TOP
      Height: 32
      Color: rgba(0 0 0 0.5)
      Padding: [2, 2, 2, 2]
      # percent
      Label {{ Text: Battery {{{{ battery.percent }}}}% }}
      If {{{{ battery.low }}}} {{
        Icon {{ Name: Warning, Size: 16px }}
      }} Else {{
        Icon {{ Name: "Ok \\u00e9" }}
      }}
      For item In {{{{ items }}}} Key {{{{ item.id }}}} {{
        Label {{ Text: {{{{ item.title }}}} }}
      }}
    }}
  }}
"""


def realistic(size: int) -> str:
    """A file of about `size` bytes (never over it) with the mix a shell file has."""
    parts = [HEAD, "Shell {\n"]
    used = len(HEAD) + len("Shell {\n") + 2
    i = 0
    while True:
        chunk = MONITOR.format(i=i)
        if used + len(chunk) > size:
            break
        parts.append(chunk)
        used += len(chunk)
        i += 1
    parts.append("}\n")
    text = "".join(parts)
    errors = tdl.parse(text).errors  # a malformed input would time the error path, not the reader
    assert errors == (), f"the benchmark input is not valid TDL: {errors[0]}"
    return text


def adversarial(size: int) -> dict[str, str]:
    """Inputs built to be slow if any step is super-linear."""
    body = size - len(HEAD) - 20
    return {
        "many {{ }} on one line": HEAD + "Shell {\n  Text: " + "{{ a }}" * (body // 7) + "\n}\n",
        "one very long word": HEAD + "Shell {\n  Text: " + "x" * body + "\n}\n",
        "long string": HEAD + 'Shell {\n  Text: "' + "x" * body + '"\n}\n',
        "huge list": HEAD + "Shell {\n  Items: [" + ", ".join(["1"] * (body // 3)) + "]\n}\n",
        "long run of }": HEAD + "Shell {\n" + "}" * (body // 1) + "\n",
        "many tiny blocks": HEAD + "Shell {\n" + "A { }\n" * (body // 6) + "}\n",
        "many comments": HEAD + "Shell {\n" + "# x\n" * (body // 4) + "}\n",
        "many mistakes (cap)": HEAD + "Shell {\n" + "Bad\n" * (body // 4) + "}\n",
        "mistakes on one line": HEAD + "Shell { " + "a: #x, " * (body // 7) + "}\n",
        "deep blocks (64)": HEAD + "B {\n" * 64 + "}\n" * 64,
    }


def best(fn, runs: int) -> float:
    fn()  # warm up
    times = []
    for _ in range(runs):
        gc.collect()
        gc.disable()
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
        gc.enable()
    return min(times)


def tree_bytes(text: str) -> int:
    """Memory the tree keeps after parsing (what `loads` returns), in bytes."""
    gc.collect()
    tracemalloc.start()
    doc = tdl.loads(text)
    kept, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del doc
    return kept


def ms(seconds: float) -> str:
    return f"{seconds * 1000:8.2f}"


def report(name: str, text: str, runs: int) -> float:
    size = len(text.encode("utf-8"))
    load = best(lambda: tdl.loads(text), runs)
    parse = best(lambda: tdl.parse(text), runs)
    doc = tdl.loads(text)
    dump = best(lambda: tdl.dumps(doc), runs)
    edit = best(lambda: doc.with_metadata("UID", "0192d3c4-0000-7000-8000-000000000001"), runs)
    kept = tree_bytes(text)
    print(
        f"{name:<26}{size:>10,} B  loads {ms(load)} ms  parse {ms(parse)} ms  "
        f"dumps {ms(dump)} ms  with_metadata {ms(edit)} ms  tree {kept / 1024:9.0f} KiB "
        f"({kept / size:5.1f}x)"
    )
    return load


def attempt(text: str):
    try:
        return tdl.loads(text)
    except tdl.TDLError:
        return None  # an adversarial input may be refused; the time to refuse is what counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=15, help="timed runs per input (best is kept)")
    runs = parser.parse_args().runs
    print(f"Python {platform.python_version()} on {platform.machine()}, tdl {tdl.__version__}")
    print(f"best of {runs} timed runs after one warm-up, GC off while timing\n")

    print("Realistic files")
    t100 = report("100 KB", realistic(100_000), runs)
    t1m = report("1 MiB (at the limit)", realistic(1_048_576), runs)

    print("\nScaling (parse time should grow about linearly)")
    base = None
    for factor in (1, 2, 4):
        text = realistic(100_000 * factor)
        load = best(lambda t=text: tdl.loads(t), runs)
        base = base or load
        size = f"{len(text):>9,} B"
        print(f"{factor}x ({size})  {ms(load)} ms   x{load / base:4.2f} (linear: x{factor})")

    print("\nAdversarial inputs (about 1 MB, refused or read)")
    inner = max(3, runs // 3)
    for name, text in adversarial(1_000_000).items():
        took = best(lambda t=text: attempt(t), inner)
        parsed = best(lambda t=text: tdl.parse(t), inner)
        print(f"{name:<26}{len(text):>10,} B  loads {ms(took)} ms  parse {ms(parsed)} ms")

    print("\nAdversarial scaling: parse time at 250 KB, 500 KB, 1 MB (linear: x2 per doubling)")
    flagged = []
    inputs = {size: adversarial(size) for size in SIZES}
    for name in inputs[SIZES[0]]:
        times = [best(lambda t=inputs[s][name]: tdl.parse(t), inner) for s in SIZES]
        r1, r2 = times[1] / times[0], times[2] / times[1]
        slow = max(r1, r2) > 3.0 and times[2] > 0.005  # tiny times are noise
        if slow:
            flagged.append(name)
        mark = "  SUPER-LINEAR" if slow else ""
        cells = " ".join(ms(t) for t in times)
        print(f"{name:<26}{cells} ms   x{r1:4.2f} x{r2:4.2f}{mark}")

    print()
    verdict_100 = "within" if t100 <= BUDGET_100K else "OVER"
    verdict_1m = "within" if t1m <= BUDGET_1M else "OVER"
    limit_100, limit_1m = BUDGET_100K * 1000, BUDGET_1M * 1000
    print(f"100 KB loads: {t100 * 1000:.2f} ms, {verdict_100} the {limit_100:.0f} ms budget")
    print(f"1 MiB loads:  {t1m * 1000:.2f} ms, {verdict_1m} the {limit_1m:.0f} ms budget")
    ok = t100 <= BUDGET_100K and t1m <= BUDGET_1M and not flagged
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
