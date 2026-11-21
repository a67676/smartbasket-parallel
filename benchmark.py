#!/usr/bin/env python3
# Benchmark script

import argparse
import csv
import os
import platform
import statistics
import time

from smartbasket_parallel import MODES, compare_results, load_mode, reference
from smartbasket_sequential import STORE_NAMES, compare_basket, cpu_info, generate_data

# CSV output columns
FIELDS = ["cpu_model", "logical_cores", "mode", "p", "N", "M", "C", "seed",
          "run", "time_s", "check", "comparisons", "failed"]


def ram_gb():
    # Retrieve the total physical RAM in gigabytes
    if platform.system() == "Windows":
        import ctypes

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                        ("page_total", ctypes.c_ulonglong), ("page_free", ctypes.c_ulonglong),
                        ("virtual_total", ctypes.c_ulonglong), ("virtual_free", ctypes.c_ulonglong),
                        ("extended_free", ctypes.c_ulonglong)]

        status = Memory()
        status.length = ctypes.sizeof(Memory)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.total / 1024 ** 3

    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3


def sequential_runs(basket, catalogs, repeats):
    # Run the sequential algorithm and record its execution time
    expected = len(basket) * len(catalogs) * len(catalogs[0])
    for r in range(repeats):
        _, t = compare_basket(basket, catalogs)
        yield r + 1, t["total"], "CORRECT", expected, ""


def parallel_runs(run, basket, catalogs, p, repeats, ref):
    # Run the parallel algorithm and measure its execution time
    for r in range(repeats):
        t0 = time.perf_counter()
        result = run(basket, catalogs, p)
        elapsed = time.perf_counter() - t0

        # Verify the parallel results against the reference results
        failed = compare_results(result, ref)
        yield r + 1, elapsed, "WRONG" if failed else "CORRECT", result.get("comparisons"), ",".join(failed)


def main():
    # Configure benchmark parameters
    ap = argparse.ArgumentParser(description="SmartBasket benchmark: every mode, every p, saved to a CSV")
    ap.add_argument("--modes", nargs="+", choices=list(MODES), default=list(MODES), help="modes to run")
    ap.add_argument("-p", "--processes", nargs="+", type=int, default=[1, 2, 4, 6, 8], help="process counts")
    ap.add_argument("-r", "--repeats", type=int, default=5, help="repeats for the sequential baseline and fix modes")
    ap.add_argument("--nosync-repeats", type=int, default=10, help="repeats for nosync")
    ap.add_argument("-n", "--items", type=int, default=100, help="N: items in the basket")
    ap.add_argument("-m", "--stores", type=int, default=4, help="M: number of stores (max 8)")
    ap.add_argument("-c", "--catalog", type=int, default=2000, help="C: listings per store")
    ap.add_argument("--seed", type=int, default=42, help="random seed (keep 42)")
    ap.add_argument("--csv", default="results/benchmark.csv", help="output CSV (overwritten on every run)")
    a = ap.parse_args()

    # Limit the number of stores to the supported range
    a.stores = max(1, min(a.stores, len(STORE_NAMES)))

    # Display system specifications and benchmark settings
    model, cores = cpu_info()
    print(f"CPU: {model}")
    print(f"Logical cores: {cores}")
    print(f"RAM: {ram_gb():.1f} GB")
    print(f"OS: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"N={a.items}, M={a.stores}, C={a.catalog}, seed={a.seed}, p={a.processes}, "
          f"repeats={a.repeats} (nosync {a.nosync_repeats}), timer=time.perf_counter()")

    # Generate the benchmark data and reference results
    basket, catalogs = generate_data(a.items, a.stores, a.catalog, a.seed)
    ref = reference(basket, catalogs)

    # Add the sequential baseline and selected parallel configurations
    configs = [("sequential", 1, None, a.repeats)]
    for name in a.modes:
        try:
            run = load_mode(name)
        except (SystemExit, ImportError) as e:
            print(f"SKIPPED {name}: {e}")
            continue
        repeats = a.nosync_repeats if name == "nosync" else a.repeats
        for p in a.processes:
            configs.append((name, p, run, repeats))

    # Save benchmark results to a CSV file
    os.makedirs(os.path.dirname(a.csv) or ".", exist_ok=True)
    with open(a.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)

        for name, p, run, repeats in configs:
            # Select the sequential or parallel execution function
            if run is None:
                rows = sequential_runs(basket, catalogs, repeats)
            else:
                rows = parallel_runs(run, basket, catalogs, p, repeats, ref)

            times, correct = [], 0
            for r, elapsed, check, comparisons, failed in rows:
                w.writerow([model, cores, name, p, len(basket), a.stores, a.catalog, a.seed,
                            r, f"{elapsed:.4f}", check, comparisons, failed])
                f.flush()
                times.append(elapsed)
                correct += check == "CORRECT"

            # Display average execution time and correctness results
            print(f"{name:<12} p={p}  mean={statistics.mean(times):.4f}s  correct={correct}/{repeats}")

    print(f"Saved to {a.csv}")


if __name__ == "__main__":
    main()
