# Benchmarks

Measured against the budget in [api.md](api.md#performance-budget): a 100 KB file in under 20 ms and a file at the 1 MiB limit in under 250 ms. The script is `benchmarks/bench.py` (standard library only, not shipped).

## Run of 2026-11-03

| | |
|---|---|
| Python | 3.14.8 |
| Machine | AMD Ryzen AI 9 HX 370 (24 threads), Linux 7.3 (CachyOS), idle |
| Code | commit `5f3da64` (step 7), `benchmarks/bench.py` as added in step 8 |
| Command | `~/Projects/pyDev/pyEnvs/tess-dl/bin/python benchmarks/bench.py --runs 15` |
| Method | best of 15 timed runs after one warm-up, garbage collector off while timing; memory by `tracemalloc` after `loads` returns |

### Budget

| Input | Size | `loads` | Budget | |
|---|---|---|---|---|
| Realistic file (monitors, bars, slots, `If`/`For`, comments) | 99,749 B | 13.11 ms | 20 ms | within |
| The same mix at the limit | 1,048,522 B | 140.30 ms | 250 ms | within |

Other calls on the same two files: `parse` 12.93 ms and 139.93 ms (the same as `loads` when there are no errors); `with_metadata` 13.09 ms and 140.78 ms (an edit rereads the whole file, so it costs one `loads`); `dumps` under 0.01 ms (it returns the stored text). The tree the reader keeps is about 19 times the size of the text (1,859 KiB for 100 KB, 19,429 KiB for 1 MiB).

### Scaling

| Input | 1x (99,749 B) | 2x | 4x |
|---|---|---|---|
| Realistic file, `loads` | 13.20 ms | 26.48 ms (x2.01) | 53.97 ms (x4.09) |

Growth is linear.

### Adversarial inputs

About 1 MB each; `parse` time at 250 KB, 500 KB and 1 MB, and the ratio per doubling (linear is x2).

| Input | 250 KB | 500 KB | 1 MB | Per doubling |
|---|---|---|---|---|
| Many `{{ a }}` on one line | 35.68 ms | 72.68 ms | 145.42 ms | x2.04, x2.00 |
| One very long word | 3.03 ms | 5.83 ms | 11.46 ms | x1.92, x1.96 |
| One long string | 0.25 ms | 0.45 ms | 0.86 ms | x1.77, x1.94 |
| A list of 330,000 numbers | 139.28 ms | 278.67 ms | 558.31 ms | x2.00, x2.00 |
| A long run of `}` | 0.13 ms | 0.14 ms | 0.14 ms | the cap stops it after 50 errors |
| Many small blocks | 52.11 ms | 105.89 ms | 214.13 ms | x2.03, x2.02 |
| Many comments | 50.10 ms | 100.67 ms | 203.12 ms | x2.01, x2.02 |
| Many mistakes, one per line (cap) | 3.13 ms | 6.14 ms | 12.46 ms | x1.96, x2.03 (the line index is built over the whole text) |
| Mistakes on one line | 0.24 ms | 0.45 ms | 0.84 ms | x1.85, x1.88 (one error: the rest of a bad line is skipped) |
| 64 levels of blocks | 0.11 ms | 0.11 ms | 0.11 ms | a size cannot grow it |

No input is super-linear. The slowest, a list of 330,000 numbers at 558 ms, is over the 250 ms figure but that figure is for a realistic file; it grows linearly and the file is at the size limit.

## What was not done

No tuning: every budget is met, so nothing was changed for speed (`perf-baseline`: no tuning before a number misses). The vault's "Performance Budgets" ledger is the maintainer's; the figures above are for a `TDL-REQ` to update it.

`tests/test_limits.py` pins the guards with generous ceilings (a 1 MiB file reads in under 3 s, about 20 times the measured time) so a quadratic step would fail the suite without making it flaky.
