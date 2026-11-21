"""
Owner: Member 5.  Mode: queue

Fix for the race conditions using a multiprocessing.Queue.

Idea: the workers do NOT touch any shared counter or shared array.
For every (item, store) pair a worker only *sends one message* to a Queue.
The parent process is the only one that reads the queue, so the parent is
the only one that updates comparisons, totals and cheapest. One writer
means no lost updates and no check-then-act problem, and no lock is needed.

Message sent by a worker (one per (item, store) pair):
    (i, s, listing, n_comparisons, cost, unit_price)
"""

from multiprocessing import Queue
from queue import Empty

from common import (build_inputs, make_pairs, chunk_size, make_pool,
                    get_shared, match_pair, line_cost, unit_price, finish)


def _worker(pair):
    """Runs inside a worker process: match one pair and send the result."""
    i, s = pair
    q = get_shared()["queue"]
    listing, n_cmp = match_pair(i, s)
    cost = line_cost(i, s, listing)        # None if the listing is unavailable
    unit = unit_price(s, listing)          # None if the listing is unavailable
    q.put((i, s, listing, n_cmp, cost, unit))


def run(basket, catalogs, p):
    n = len(basket)
    m = len(catalogs)

    item_grams, indexes = build_inputs(basket, catalogs)

    # The queue is created inside run() and sent to the workers through the
    # pool initializer (inside the shared dict), never as a global variable.
    queue = Queue()
    shared = {"queue": queue}

    pairs = make_pairs(n, m)

    # Results are built ONLY from the queue messages (the parent is the only writer).
    matched = [[-1] * m for _ in range(n)]
    comparisons = 0
    totals = [0.0] * m
    cheapest = [None] * n

    with make_pool(p, basket, catalogs, item_grams, indexes, shared) as pool:
        # map_async: the parent must be free to read the queue while workers run.
        # (Reading only after the pool has been closed could lose messages.)
        async_result = pool.map_async(_worker, pairs,
                                      chunksize=chunk_size(len(pairs), p))

        received = 0
        while received < len(pairs):
            try:
                i, s, listing, n_cmp, cost, unit = queue.get(timeout=1)
            except Empty:
                if async_result.ready():
                    async_result.get()     # re-raises an error from a worker
                continue
            received += 1

            matched[i][s] = listing
            comparisons += n_cmp
            if cost is not None:
                totals[s] += cost
            if unit is not None:
                # same rule as the sequential min((price, store)): lowest price,
                # and the lower store number wins a tie
                if cheapest[i] is None or (unit, s) < cheapest[i]:
                    cheapest[i] = (unit, s)

        async_result.get()

    queue.close()
    return finish(basket, catalogs, matched, comparisons, totals, cheapest)
