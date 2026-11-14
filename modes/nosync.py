# Members 2 and 3: unsynchronised mode (shared variables, race conditions)
#
# Member 2 (Razan): shared variable comparison_counter.
#   Every worker adds 1 to it for every Jaccard calculation, with NO lock.
#   counter.value += 1 is three steps (read, add, write), so two processes can
#   read the same value and one update is lost. The final count is then
#   below the correct value (N x M x C = 800,000 by default).
#
# Member 3: add store_totals and cheapest_price / cheapest_store below.

from multiprocessing import Value

import common


def _worker(pair):
    i, s = pair
    shared = common.get_shared()

    # match one (item, store) pair with the Stage 1 best_match()
    best_listing, n_comparisons = common.match_pair(i, s)

    # RACE: +1 for every Jaccard calculation, without a lock
    counter = shared["comparison_counter"]
    for _ in range(n_comparisons):
        counter.value += 1          # read -> add 1 -> write (not atomic)

    return i, s, best_listing


def run(basket, catalogs, p):
    n = len(basket)
    m = len(catalogs)
    item_grams, indexes = common.build_inputs(basket, catalogs)

    # shared variable, created inside run() and sent to the workers
    shared = {"comparison_counter": Value("i", 0)}

    pairs = common.make_pairs(n, m)
    with common.make_pool(p, basket, catalogs, item_grams, indexes, shared) as pool:
        results = pool.map(_worker, pairs, chunksize=common.chunk_size(len(pairs), p))

    matched = [[None] * m for _ in range(n)]
    for i, s, best_listing in results:
        matched[i][s] = best_listing

    comparisons = shared["comparison_counter"].value

    # TEMPORARY (until Member 3 adds her shared variables):
    # totals and cheapest are computed here in the parent, so they are correct.
    totals = [0] * m
    cheapest = [None] * n
    for i in range(n):
        for s in range(m):
            listing = catalogs[s][matched[i][s]]
            if listing["available"]:
                totals[s] += listing["price"] * basket[i]["qty"]
                if cheapest[i] is None or (listing["price"], s) < cheapest[i]:
                    cheapest[i] = (listing["price"], s)

    return common.finish(basket, catalogs, matched, comparisons, totals, cheapest)

