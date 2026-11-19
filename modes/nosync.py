
# Members 2 and 3: unsynchronised mode (shared variables, race conditions)
#
# Member 2 (Razan): shared variable comparison_counter.
# Member 3: store_totals and cheapest_price / cheapest_store.

from multiprocessing import Value, Array
import math

import common


def _worker(pair):
    i, s = pair
    shared = common.get_shared()

    # match one (item, store) pair with Stage 1 best_match()
    best_listing, n_comparisons = common.match_pair(i, s)

    # Member 2: comparison counter race
    counter = shared["comparison_counter"]
    for _ in range(n_comparisons):
        counter.value += 1

    # Member 3: shared store totals race
    cost = common.line_cost(i, s, best_listing)

    if cost is not None:
        totals = shared["store_totals"]
        totals[s] += cost

        # Member 3: cheapest price/store race
        price = common.unit_price(s, best_listing)
        cheapest_price = shared["cheapest_price"]
        cheapest_store = shared["cheapest_store"]

        current_price = cheapest_price[i]
        current_store = cheapest_store[i]

        # Check-then-act without a lock
        if (price, s) < (current_price, current_store):
            cheapest_price[i] = price
            cheapest_store[i] = s

    return i, s, best_listing


def run(basket, catalogs, p):
    n = len(basket)
    m = len(catalogs)

    item_grams, indexes = common.build_inputs(basket, catalogs)

    # Shared variables created inside run()
    shared = {
        "comparison_counter": Value("i", 0),
        "store_totals": Array("d", [0.0] * m),
        "cheapest_price": Array("d", [math.inf] * n),
        "cheapest_store": Array("i", [m] * n),
    }

    pairs = common.make_pairs(n, m)

    with common.make_pool(
        p, basket, catalogs, item_grams, indexes, shared
    ) as pool:
        results = pool.map(
            _worker,
            pairs,
            chunksize=common.chunk_size(len(pairs), p),
        )

    matched = [[None] * m for _ in range(n)]
    for i, s, best_listing in results:
        matched[i][s] = best_listing

    comparisons = shared["comparison_counter"].value
    totals = list(shared["store_totals"])

    cheapest = []
    for i in range(n):
        price = shared["cheapest_price"][i]
        store = shared["cheapest_store"][i]

        if math.isinf(price):
            cheapest.append(None)
        else:
            cheapest.append((price, store))

    return common.finish(
        basket, catalogs, matched, comparisons, totals, cheapest
    )

