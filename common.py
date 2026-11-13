"""

Owner: Member 1 (Aseel). Other members import from this file but do not edit it.

Functions Included:
  build_inputs() : trigram index of every store + every basket item (done in the parent)
  make_pairs() : the N x M independent (item, store) tasks
  chunk_size() : how many tasks each worker takes at a time
  make_pool()  : creates the worker processes and sends them the data ONCE
  get_shared() : inside a worker: returns the shared objects your mode passed in
  match_pair() : inside a worker: matches one (item, store) pair
  line_cost()  : inside a worker: price x quantity of one matched pair (None if unavailable)
  unit_price() : inside a worker: unit price of one matched pair (None if unavailable)
  finish()     : in the parent: builds the final result dictionary (steps 2-6)

How a mode uses it (inside run(basket, catalogs, p)):
  1. item_grams, indexes = build_inputs(basket, catalogs)
  2. create shared objects (Value, Array, Lock, Queue) and put them in a dict
  3. with make_pool(p, basket, catalogs, item_grams, indexes, shared) as pool:
         results = pool.map(your_worker_function, make_pairs(...), chunksize=...)
  4. return finish(basket, catalogs, matched, comparisons, totals, cheapest)
"""
import math
from multiprocessing import Pool

from smartbasket_sequential import trigrams, best_match



# Parent side

def build_inputs(basket, catalogs):
    #Trigram sets of every store listing and every basket item.
    indexes = []
    for cat in catalogs:                      # every store
        store_index = []
        for listing in cat:                   # every listing in that store
            store_index.append(trigrams(listing["name"]))
        indexes.append(store_index)

    item_grams = []
    for item in basket:                       # every basket item
        item_grams.append(trigrams(item["name"]))

    return item_grams, indexes


def make_pairs(n_items, n_stores):
    #All N x M (item, store) tasks. Each one is independent of the others.
    pairs = []
    for i in range(n_items):
        for s in range(n_stores):
            pairs.append((i, s))
    return pairs


def chunk_size(n_tasks, p):
    #About 4 chunks per worker (inspired from Python's default for Pool.map).
    return max(1, math.ceil(n_tasks / (4 * p)))


def make_pool(p, basket, catalogs, item_grams, indexes, shared=None):

    prices = []
    # each store
    for cat in catalogs:                      
        store_prices = []
        # every listing
        for listing in cat:                   
            if listing["available"]:
                store_prices.append(listing["price"])
            else:
                store_prices.append(None)
        prices.append(store_prices)

    qtys = []
    for item in basket:
        qtys.append(item["qty"])

    if shared is None:
        shared = {}

    return Pool(processes=p, initializer=_init_worker,
                initargs=(item_grams, indexes, prices, qtys, shared))


# Worker side (these run inside the worker processes)
# every worker fills this once in _init_worker
_W = {} 


def _init_worker(item_grams, indexes, prices, qtys, shared):
    _W["item_grams"] = item_grams
    _W["indexes"] = indexes
    _W["prices"] = prices
    _W["qtys"] = qtys
    _W["shared"] = shared


def get_shared():
    # The dict of shared objects passed to make_pool().
    return _W["shared"]


def match_pair(i, s):
    
    # for every basket item i match it against every listing of store s.
    # Returns (best_listing_index, number_of_comparisons).
    
    index = _W["indexes"][s]
    best_listing = best_match(_W["item_grams"][i], index)
    return best_listing, len(index)


def line_cost(i, s, listing):
    # Price x quantity of the matched listing, or None if it is unavailable.
    price = _W["prices"][s][listing]
    if price is None:
        return None
    return price * _W["qtys"][i]


def unit_price(s, listing):
    # Unit price of the matched listing, or None if it is unavailable.
    return _W["prices"][s][listing]



# Parent side

def finish(basket, catalogs, matched, comparisons, totals, cheapest):

    n = len(basket)
    m = len(catalogs)

    # accuracy: how many pairs matched the correct product
    correct = 0
    for i in range(n):
        for s in range(m):
            listing = catalogs[s][matched[i][s]]
            if listing["pid"] == basket[i]["pid"]:
                correct += 1

    # complete[s] is True only if every item is available in store s
    complete = []
    for s in range(m):
        store_complete = True
        for i in range(n):
            listing = catalogs[s][matched[i][s]]
            if not listing["available"]:
                store_complete = False
                break
        complete.append(store_complete)

    # cheapest complete basketr
    best_store = None
    for s in range(m):
        if complete[s]:
            if best_store is None or totals[s] < totals[best_store]:
                best_store = s

    # smart split: only possible if every single item is available in some store
    split_possible = True
    for i in range(n):
        if cheapest[i] is None:
            split_possible = False
            break

    split_total = None
    if split_possible:
        split_total = 0.0
        for i in range(n):
            unit, store = cheapest[i]
            split_total += unit * basket[i]["qty"]

    saving = None
    if best_store is not None and split_possible:
        saving = totals[best_store] - split_total

    # convert to normal lists 
    matched_copy = []
    for i in range(n):
        matched_copy.append(list(matched[i]))

    return {
        "matched": matched_copy,
        "comparisons": comparisons,
        "totals": list(totals),
        "cheapest": list(cheapest),
        "complete": complete,
        "best_store": best_store,
        "split_total": split_total,
        "saving": saving,
        "accuracy": correct / (n * m),
    }
