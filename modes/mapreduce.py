# Member 6: map-reduce mode

import common


def _map_pair(pair):
    """Process one item-store pair and return its local results."""
    i, s = pair

    best_listing, n_comparisons = common.match_pair(i, s)
    cost = common.line_cost(i, s, best_listing)
    price = common.unit_price(s, best_listing)

    return i, s, best_listing, n_comparisons, cost, price


def run(basket, catalogs, p):
    """Run SmartBasket using Map-Reduce."""

    n = len(basket)
    m = len(catalogs)

    # Prepare indexes and tasks
    item_grams, indexes = common.build_inputs(basket, catalogs)
    pairs = common.make_pairs(n, m)

    # MAP: workers process tasks independently
    with common.make_pool(p, basket, catalogs, item_grams, indexes) as pool:
        mapped_results = pool.map(
            _map_pair,
            pairs,
            chunksize=common.chunk_size(len(pairs), p),
        )

    # REDUCE: parent combines the returned results
    matched = [[None] * m for _ in range(n)]
    comparisons = 0
    totals = [0.0] * m
    cheapest = [None] * n

    for i, s, best_listing, n_comparisons, cost, price in mapped_results:

        matched[i][s] = best_listing
        comparisons += n_comparisons

        if cost is not None:
            totals[s] += cost

            candidate = (price, s)

            if cheapest[i] is None or candidate < cheapest[i]:
                cheapest[i] = candidate

    # Return the standard result dictionary
    return common.finish(
        basket,
        catalogs,
        matched,
        comparisons,
        totals,
        cheapest
    )