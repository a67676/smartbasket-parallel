# SmartBasket – Parallel version (Assignment 2)

Parallel version of our Stage 1 SmartBasket code, used to study race conditions
and compare four ways of fixing them. Python 3, standard library only.

## Files

| File | Owner | Purpose |
| --- | --- | --- |
| `smartbasket_sequential.py` | Stage 1 | Sequential baseline. **Do not edit.** |
| `common.py` | Member 1 | Shared helpers: indexes, pool, task list, steps 2–6. **Do not edit; ask Member 1.** |
| `smartbasket_parallel.py` | Member 1 | Command line, timing, correctness check, list of modes |
| `modes/nosync.py` | Members 2 and 3 | No synchronisation (shows the race conditions) |
| `modes/lock.py` | Member 4 | `lock` and `lock_batched` modes |
| `modes/queue_mode.py` | Member 5 | `queue` mode |
| `modes/mapreduce.py` | Member 6 | `mapreduce` mode |
| `benchmark.py` | Member 7 | Runs every mode and saves the times to a CSV |
| `results/` | Members 2, 3, 7 | CSV files and screenshots |

## How to run

    python smartbasket_parallel.py --mode lock -p 4
    python smartbasket_parallel.py --mode nosync -p 8 -r 10

Options: `--mode` (nosync, lock, lock_batched, queue, mapreduce), `-p` processes,
`-r` repeats, and the Stage 1 options `-n`, `-m`, `-c`, `--seed`.
Always keep seed 42 and the defaults N = 100, M = 4, C = 2,000 unless told otherwise.

## The rules every mode must follow

### 1. One function, always the same signature

Every mode file contains this function:

    def run(basket, catalogs, p):
        ...
        return result

- `basket`, `catalogs`: the inputs from `generate_data()` (already created, not timed)
- `p`: number of worker processes
- `result`: a dictionary with the keys listed in rule 3
  
Exception: modes/lock.py contains two functions with this signature, run_lock() and run_lock_batched().
Do **not** time anything inside `run()`. `smartbasket_parallel.py` times the whole call.

### 2. Reuse the existing code, never copy it

- Import the matching functions from the sequential file:
  `from smartbasket_sequential import trigrams, similarity, best_match`
- Import the shared helpers from `common.py` (pool creation, task list, steps 2–6).

Using identical matching code means any wrong result can only come from the race,
not from a typo in a copied function.

### 3. What `result` must contain

| Key | Meaning | Correct value |
| --- | --- | --- |
| `matched` | Best listing for every (item, store) pair | Same as sequential |
| `comparisons` | Total number of Jaccard calculations | Exactly N × M × C (800,000 by default) |
| `totals` | Basket total per store | Same as sequential |
| `cheapest` | Cheapest (price, store) per item | Same as sequential |
| `complete`, `best_store`, `split_total`, `saving`, `accuracy` | Same meaning as in Stage 1 | Same as sequential |

`comparisons`, `totals` and `cheapest` are the three **studied variables**. They must
come from **your mode's own method** (a shared variable, a lock, a queue or a
reduction). Never recompute them from `matched` at the end, or the race disappears.

### 4. Shared variables

- Create shared variables (`multiprocessing.Value`, `Array`, `Lock`, `Queue`) **inside `run()`**.
- Pass them to the workers through the pool's `initializer` (a helper in `common.py`
  does this). **Never** use plain global variables: they do not work on Windows or macOS.
- Keep `if __name__ == "__main__":` in any file you run directly.

### 5. Output format

`smartbasket_parallel.py` prints one line per run. Do not print anything else from your mode.

    MODE=lock P=4 RUN=1 TIME=1.2345 CHECK=CORRECT COMPARISONS=800000
When CHECK=WRONG, a FAILED= field lists the wrong keys, e.g.                         FAILED=comparisons,totals. 
Add --csv results/runs.csv to save every run to a CSV file.
`CHECK` is `CORRECT` when every key in rule 3 matches the sequential result
(prices compared with a tolerance of 1e-9), otherwise `WRONG`.

## Branches and merging

| Member | Branch |
| --- | --- |
| 1 | `member1-base` |
| 2 | `member2-counter` |
| 3 | `member3-totals` |
| 4 | `member4-lock` |
| 5 | `member5-queue` |
| 6 | `member6-mapreduce` |
| 7 | `member7-benchmark` |

Members 2 and 3 share `modes/nosync.py`: Member 2 adds `comparisons`, then Member 3
adds `totals` and `cheapest` on top. Member 3, pull Member 2's merged version first.

**Before you merge your own branch into `main`, check all of these:**

- [ ] You pulled the latest `main` into your branch first (no conflicts)
- [ ] You changed **only your own file(s)**
- [ ] Your mode runs at `-p 2` and `-p 4` without errors
- [ ] Fix modes (`lock`, `lock_batched`, `queue`, `mapreduce`): `CHECK=CORRECT` in **5 out of 5** runs
- [ ] `nosync`: runs without crashing; `CHECK=WRONG` in at least some runs

Then open a pull request from your branch into `main` and merge it yourself.

## Deadlines

- Base version and `common.py` ready (Member 1): 12-11-26
- All modes merged into `main`: 17-11-26
- After that, the code is frozen and tagged `v1.0` for benchmarking. No changes after the tag.
