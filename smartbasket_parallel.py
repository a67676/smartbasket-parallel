#!/usr/bin/env python3



# Owner: Member 1 (Aseel).

# This code runs one parallel mode, times it, and checks its result against the sequential result.


import argparse
import csv
import importlib
import math
import os
import platform
import statistics
import time

import common
from smartbasket_sequential import STORE_NAMES, generate_data, compare_basket, best_match, cpu_info

# dictionary that maps mode name to corresponding file
MODES = {
    "nosync":       ("modes.nosync", "run"),
    "lock":         ("modes.lock", "run_lock"),
    "lock_batched": ("modes.lock", "run_lock_batched"),
    "queue":        ("modes.queue_mode", "run"),
    "mapreduce":    ("modes.mapreduce", "run"),
}
#two prices are considered equal if they differ by less than one billionth of their size
TOLERANCE = 1e-9 


# Loading a mode
def load_mode(name):
    
    module_name, function_name = MODES[name]
    module = importlib.import_module(module_name)
    if not hasattr(module, function_name):
        raise SystemExit(f"{module_name.replace('.', '/')}.py has no function {function_name}()."
                        f"Mode '{name}' may not be implemented yet. ")
    return getattr(module, function_name)



# The correct answer (sequential)
def reference(basket, catalogs):
    n = len(basket)
    m = len(catalogs)
    item_grams, indexes = common.build_inputs(basket, catalogs)

    matched = []
    comparisons = 0
    for i in range(n):
        row = []
        for s in range(m):
            row.append(best_match(item_grams[i], indexes[s]))
            comparisons += len(indexes[s])
        matched.append(row)

    totals = [0] * m
    cheapest = [None] * n
    for i in range(n):
        for s in range(m):
            listing = catalogs[s][matched[i][s]]
            if listing["available"]:
                totals[s] += listing["price"] * basket[i]["qty"]
                if cheapest[i] is None or (listing["price"], s) < cheapest[i]:
                    cheapest[i] = (listing["price"], s)

    ref = common.finish(basket, catalogs, matched, comparisons, totals, cheapest)

    # safety check: the reference must agree with the Stage 1 result
    stage1, _ = compare_basket(basket, catalogs)
    failed = compare_results(ref, stage1, keys=("totals", "complete", "best_store",
                                                "split_total", "saving", "accuracy"))
    if failed:
        raise SystemExit(f"Internal error: reference disagrees with Stage 1 on {failed}.")
    return ref


# Correctness check

def same_number(a, b):
    #True if both are None, or both are numbers equal within the tolerance.
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=TOLERANCE)


def compare_results(par, ref, keys=None):
    #Return the list of result keys where par differs from ref (empty list = CORRECT).
    if keys is None:
        keys = ("matched", "comparisons", "totals", "cheapest", "complete",
                "best_store", "split_total", "saving", "accuracy")
    failed = []
    for key in keys:
        a = par.get(key)
        b = ref.get(key)

        if key == "totals":
            ok = a is not None and len(a) == len(b)
            if ok:
                for s in range(len(b)):
                    if not same_number(a[s], b[s]):
                        ok = False
                        break

        elif key == "cheapest":
            ok = a is not None and len(a) == len(b)
            if ok:
                for i in range(len(b)):
                    if a[i] is None or b[i] is None:
                        if not (a[i] is None and b[i] is None):
                            ok = False
                            break
                    elif not same_number(a[i][0], b[i][0]) or a[i][1] != b[i][1]:
                        ok = False
                        break

        elif key in ("split_total", "saving"):
            ok = same_number(a, b)

        else:  # finally, check: matched, comparisons, complete, best_store, accuracy
            ok = a == b

        if not ok:
            failed.append(key)
    return failed



def main():
    ap = argparse.ArgumentParser(description="SmartBasket parallel benchmark")
    ap.add_argument("--mode", required=True, choices=list(MODES), help="which parallel version to run")
    ap.add_argument("-p", "--processes", type=int, default=2, help="number of worker processes")
    ap.add_argument("-n", "--items", type=int, default=100, help="N: items in the basket")
    ap.add_argument("-m", "--stores", type=int, default=4, help="M: number of stores (max 8)")
    ap.add_argument("-c", "--catalog", type=int, default=2000, help="C: listings per store")
    ap.add_argument("-r", "--repeats", type=int, default=5, help="number of timed repetitions")
    ap.add_argument("--seed", type=int, default=42, help="random seed (keep 42)")
    ap.add_argument("--csv", help="append one row per run to this CSV file")
    a = ap.parse_args()
    a.stores = max(1, min(a.stores, len(STORE_NAMES)))

    model, cores = cpu_info()
    print(f"CPU: {model} | logical cores: {cores} | Python {platform.python_version()} | {platform.system()}")
    print(f"mode={a.mode}, p={a.processes}, N={a.items}, M={a.stores}, C={a.catalog}, "
          f"repeats={a.repeats}, seed={a.seed}")
    if cores and a.processes > cores:
        print(f"WARNING: p={a.processes} is more than the {cores} logical cores on this machine.")

    run = load_mode(a.mode)
    basket, catalogs = generate_data(a.items, a.stores, a.catalog, a.seed)  # not timed
    ref = reference(basket, catalogs)                                        # not timed

    times = []
    n_correct = 0
    for r in range(a.repeats):
        t0 = time.perf_counter()
        result = run(basket, catalogs, a.processes)                          # TIMED
        elapsed = time.perf_counter() - t0

        failed = compare_results(result, ref)
        check = "CORRECT" if not failed else "WRONG"
        if not failed:
            n_correct += 1
        times.append(elapsed)

        line = (f"MODE={a.mode} P={a.processes} RUN={r + 1} TIME={elapsed:.4f} "
                f"CHECK={check} COMPARISONS={result.get('comparisons')}")
        if failed:
            line += f" FAILED={','.join(failed)}"
        print(line)

        if a.csv:
            new_file = not os.path.exists(a.csv)
            with open(a.csv, "a", newline="") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(["cpu_model", "logical_cores", "mode", "p", "N", "M", "C", "seed",
                                "run", "time_s", "check", "comparisons", "failed"])
                w.writerow([model, cores, a.mode, a.processes, len(basket), a.stores, a.catalog,
                            a.seed, r + 1, f"{elapsed:.4f}", check, result.get("comparisons"),
                            ",".join(failed)])

    mean = statistics.mean(times)
    sd = statistics.stdev(times) if len(times) > 1 else 0.0
    print(f"\nSummary: mean={mean:.4f}s  min={min(times):.4f}s  max={max(times):.4f}s  "
          f"std={sd:.4f}s  correct={n_correct}/{a.repeats}")
    if a.csv:
        print(f"Rows appended to {a.csv}")


if __name__ == "__main__":
    main()
