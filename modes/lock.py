"""
Owner: Member 4 (Najah).

Two lock-based fixes for the three studied variables:
  run_lock()          : take the lock around EVERY single shared update
  run_lock_batched()  : add up locally, take the lock ONCE per chunk of tasks

Shared variables (created inside run_..., passed to workers through common.make_pool):
  comparisons          Value  'q'  total Jaccard calculations      (read-modify-write)
  totals[s]            Array  'd'  basket total of store s          (read-modify-write)
  cheapest_price[i]    Array  'd'  cheapest unit price of item i    (check-then-act)
  cheapest_store[i]    Array  'i'  store of that cheapest price     (check-then-act)
"""
from multiprocessing import Array, Lock, Value

from common import (build_inputs, chunk_size, finish, get_shared, line_cost,
                    make_pairs, make_pool, match_pair, unit_price)

NO_STORE = -1   # cheapest_store value meaning "not available in any store yet"


# ---------------------------------------------------------------------------------------
# Helpers used by both modes
# ---------------------------------------------------------------------------------------
def _create_shared(n, m):
    # lock=False: we do NOT rely on the objects' built-in locks; our own Lock protects them.
    return {
        "lock": Lock(),
        "comparisons": Value("q", 0, lock=False),
        "totals": Array("d", m, lock=False),                      # all 0.0
        "cheapest_price": Array("d", [float("inf")] * n, lock=False),
        "cheapest_store": Array("i", [NO_STORE] * n, lock=False),
    }


def _collect(basket, catalogs, shared, matches):
    # Parent side: read the shared variables and build the result dictionary.
    n, m = len(basket), len(catalogs)
    matched = [[None] * m for _ in range(n)]
    for i, s, listing in matches:
        matched[i][s] = listing

    cheapest = []
    for i in range(n):
        store = shared["cheapest_store"][i]
        cheapest.append(None if store == NO_STORE else (shared["cheapest_price"][i], store))

    return finish(basket, catalogs, matched, shared["comparisons"].value,
                  list(shared["totals"]), cheapest)


# ---------------------------------------------------------------------------------------
# Mode "lock": one lock acquisition around every single update
# ---------------------------------------------------------------------------------------
def _worker_lock(pair):
    i, s = pair
    sh = get_shared()
    lock = sh["lock"]

    listing, n_comp = match_pair(i, s)      # the heavy work, no shared state touched

    for _ in range(n_comp):                 # update 1: comparison counter, +1 per comparison
        with lock:                          # (same 800,000 updates as nosync, each one locked)
            sh["comparisons"].value += 1

    cost = line_cost(i, s, listing)
    if cost is not None:                    # item available in this store
        with lock:                          # update 2: store total
            sh["totals"][s] += cost

        price = unit_price(s, listing)
        with lock:                          # update 3: check AND act inside the same lock
            if (price, s) < (sh["cheapest_price"][i], sh["cheapest_store"][i]):
                sh["cheapest_price"][i] = price
                sh["cheapest_store"][i] = s

    return i, s, listing


def run_lock(basket, catalogs, p):
    n, m = len(basket), len(catalogs)
    item_grams, indexes = build_inputs(basket, catalogs)
    shared = _create_shared(n, m)
    pairs = make_pairs(n, m)

    with make_pool(p, basket, catalogs, item_grams, indexes, shared) as pool:
        matches = pool.map(_worker_lock, pairs, chunksize=chunk_size(len(pairs), p))

    return _collect(basket, catalogs, shared, matches)


# ---------------------------------------------------------------------------------------
# Mode "lock_batched": private local results, ONE lock acquisition per chunk
# ---------------------------------------------------------------------------------------
def _worker_batched(chunk):
    sh = get_shared()

    # 1. do the whole chunk privately (no lock, nobody else sees these variables)
    local_comp = 0
    local_totals = {}                       # store -> sum of price x qty
    local_cheapest = {}                     # item  -> (price, store)
    matches = []
    for i, s in chunk:
        listing, n_comp = match_pair(i, s)
        matches.append((i, s, listing))
        local_comp += n_comp

        cost = line_cost(i, s, listing)
        if cost is not None:
            local_totals[s] = local_totals.get(s, 0.0) + cost
            candidate = (unit_price(s, listing), s)
            if i not in local_cheapest or candidate < local_cheapest[i]:
                local_cheapest[i] = candidate

    # 2. merge into the shared variables, taking the lock only once
    with sh["lock"]:
        sh["comparisons"].value += local_comp
        for s, subtotal in local_totals.items():
            sh["totals"][s] += subtotal
        for i, (price, s) in local_cheapest.items():
            if (price, s) < (sh["cheapest_price"][i], sh["cheapest_store"][i]):
                sh["cheapest_price"][i] = price
                sh["cheapest_store"][i] = s

    return matches


def run_lock_batched(basket, catalogs, p):
    n, m = len(basket), len(catalogs)
    item_grams, indexes = build_inputs(basket, catalogs)
    shared = _create_shared(n, m)
    pairs = make_pairs(n, m)

    # group the tasks into chunks ourselves, so each worker call = one chunk = one lock
    size = chunk_size(len(pairs), p)
    chunks = [pairs[k:k + size] for k in range(0, len(pairs), size)]

    with make_pool(p, basket, catalogs, item_grams, indexes, shared) as pool:
        per_chunk = pool.map(_worker_batched, chunks, chunksize=1)

    matches = [x for chunk_matches in per_chunk for x in chunk_matches]
    return _collect(basket, catalogs, shared, matches)
