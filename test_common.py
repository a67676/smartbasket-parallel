#Quick test for common.py by Member 1(Aseel).


import math
import multiprocessing as mp
import sys
import time

import common
from smartbasket_sequential import generate_data, compare_basket


def worker(pair):
    #One (item, store) task: match it and return everything the parent needs
    i, s = pair
    listing, n_comp = common.match_pair(i, s)
    return i, s, listing, n_comp, common.line_cost(i, s, listing), common.unit_price(s, listing)


def run_simple(basket, catalogs, p):
    n, m = len(basket), len(catalogs)
    item_grams, indexes = common.build_inputs(basket, catalogs)
    pairs = common.make_pairs(n, m)
    with common.make_pool(p, basket, catalogs, item_grams, indexes) as pool:
        results = pool.map(worker, pairs, chunksize=common.chunk_size(len(pairs), p))

    # combine the results in the parent
    matched = [[None] * m for _ in range(n)]
    comparisons, totals, cheapest = 0, [0] * m, [None] * n
    for i, s, listing, n_comp, cost, price in sorted(results):
        matched[i][s] = listing
        comparisons += n_comp
        if cost is not None:
            totals[s] += cost
            if cheapest[i] is None or (price, s) < cheapest[i]:
                cheapest[i] = (price, s)
    return common.finish(basket, catalogs, matched, comparisons, totals, cheapest)


def main():
    n, m, c = 100, 4, 2000
    basket, catalogs = generate_data(n, m, c, 42)
    seq, t = compare_basket(basket, catalogs)
    print(f"sequential: {t['total']:.3f} s")

    ok_all = True
    for p in (1, 2, 4):
        t0 = time.perf_counter()
        par = run_simple(basket, catalogs, p)
        elapsed = time.perf_counter() - t0
        ok = (par["comparisons"] == n * m * c
              and all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(par["totals"], seq["totals"]))
              and par["complete"] == seq["complete"]
              and par["best_store"] == seq["best_store"]
              and math.isclose(par["split_total"], seq["split_total"], rel_tol=1e-9)
              and math.isclose(par["saving"], seq["saving"], rel_tol=1e-9)
              and par["accuracy"] == seq["accuracy"])
        ok_all &= ok
        print(f"p={p}: {elapsed:.3f} s  {'CORRECT' if ok else 'WRONG'}")
    sys.exit(0 if ok_all else 1)

#imitating windows or mac startup process
if __name__ == "__main__":
    if "--spawn" in sys.argv:          
        mp.set_start_method("spawn")
    main()
