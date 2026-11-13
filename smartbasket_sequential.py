#!/usr/bin/env python3
"""
SmartBasket - SEQUENTIAL version (ARTI503 Project Stage 1)

What it does (the "Compare" step of the app):
  1. Product matching  : link every basket item to its equivalent listing in every store
                         (character-trigram Jaccard similarity against ALL listings of the store)
  2. Price lookup      : read price + availability of each matched listing
  3. Basket totals     : total per store (available items only)
  4. Complete baskets  : stores having every item; pick the cheapest one
  5. Cheapest per item : cheapest store for each item
  6. Smart split       : buy each item from its cheapest store, compare with best single store

Input size is adjustable: N = items in basket, M = stores, C = listings per store.
Data is synthetic (generated with a fixed seed so every member gets the SAME input).
Only the Python standard library is used.

Examples:
  python smartbasket_sequential.py                       # N=100, M=4, C=2000, 5 repeats
  python smartbasket_sequential.py -n 200 -m 8 -c 5000 -r 10
  python smartbasket_sequential.py --csv results.csv     # append a result row to a CSV
"""
import argparse
import csv
import os
import platform
import random
import statistics
import time

STORE_NAMES = ["Ninja", "Lulu", "Panda", "Othaim", "Tamimi", "Carrefour", "Danube", "Farm"]
BRANDS = ["Almarai", "Nadec", "Sadafco", "Alsafi", "Lusine", "Americana", "Kinza", "Saudia",
          "Freshly", "Goody", "Heinz", "Nestle", "Lipton", "Tang", "Indomie", "Kraft",
          "Puck", "President", "Activia", "Baladna"]
TYPES = ["Full Fat Milk", "Low Fat Milk", "Toast Bread", "Cheddar Cheese", "Cream Cheese",
         "Orange Juice", "Apple Juice", "Basmati Rice", "White Sugar", "Sunflower Oil",
         "Olive Oil", "Tomato Paste", "Black Tea", "Instant Coffee", "Plain Yogurt",
         "Chicken Nuggets", "Frozen Peas", "Corn Flakes", "Tuna Chunks", "Mineral Water",
         "Strawberry Jam", "Butter", "Pasta Penne", "Chickpeas", "Hummus",
         "Laban Drink", "Mayonnaise", "Ketchup", "Cooking Cream", "Fava Beans"]
SIZES = ["200g", "250g", "400g", "500g", "1kg", "2kg", "330ml", "500ml", "1L", "2L"]
FLAVOURS = ["", "Classic", "Light", "Organic", "Family Pack", "Extra", "Premium", "Mild", "Original",
            "Select"]


# ---------------------------------------------------------------------------------------
# Synthetic data (NOT timed)
# ---------------------------------------------------------------------------------------
def canonical_name(pid):
    """Unique (brand, type, size, flavour) for every product id."""
    b = BRANDS[pid % len(BRANDS)]
    t = TYPES[(pid // len(BRANDS)) % len(TYPES)]
    s = SIZES[(pid // (len(BRANDS) * len(TYPES))) % len(SIZES)]
    f = FLAVOURS[(pid // (len(BRANDS) * len(TYPES) * len(SIZES))) % len(FLAVOURS)]
    return b, t, s, f


def store_variant(parts, style, rng):
    """Each store writes the same product differently (word order, case, separators, typos)."""
    b, t, s, f = parts
    f = f if f else ""
    if style == 0:
        name = f"{b} {t} {f} {s}"
    elif style == 1:
        name = f"{t} {b} {s} {f}".lower()
    elif style == 2:
        name = f"{b} - {t} ({s}) {f}"
    elif style == 3:
        name = f"{t}, {b}, {f} {s}".upper()
    else:
        name = f"{b} {f} {t} {s}"
    name = " ".join(name.split())
    if rng.random() < 0.10 and len(name) > 6:  # 10% of listings contain a typo
        i = rng.randrange(1, len(name) - 1)
        name = name[:i] + name[i + 1:]
    return name


def generate_data(n_items, n_stores, catalog_size, seed):
    rng = random.Random(seed)
    n_items = min(n_items, catalog_size)
    base_price = [round(rng.uniform(2, 60), 2) for _ in range(catalog_size)]
    catalogs = []  # per store: list of dicts {name, price, available, pid}
    for s in range(n_stores):
        listings = []
        for pid in range(catalog_size):
            listings.append({
                "name": store_variant(canonical_name(pid), s % 5, rng),
                "price": round(base_price[pid] * rng.uniform(0.85, 1.15), 2),
                "available": rng.random() < 0.97,
                "pid": pid,  # ground truth, used ONLY to check accuracy
            })
        rng.shuffle(listings)
        catalogs.append(listings)
    chosen = rng.sample(range(catalog_size), n_items)
    basket = []
    for pid in chosen:
        b, t, s, f = canonical_name(pid)
        basket.append({"name": " ".join(f"{b} {t} {f} {s}".split()),
                       "qty": rng.randint(1, 3), "pid": pid})
    return basket, catalogs


# ---------------------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------------------
def trigrams(text):
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    cleaned = " ".join(cleaned.split())
    padded = f"  {cleaned} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def similarity(a, b):
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter) if inter else 0.0


def best_match(item_grams, store_index):
    """Compare the item against EVERY listing of the store (the heavy part)."""
    best_i, best_s = -1, -1.0
    for i, grams in enumerate(store_index):
        sc = similarity(item_grams, grams)
        if sc > best_s:
            best_i, best_s = i, sc
    return best_i


# ---------------------------------------------------------------------------------------
# The sequential comparison (TIMED)
# ---------------------------------------------------------------------------------------
def compare_basket(basket, catalogs):
    t = {}
    t0 = time.perf_counter()

    # 0. preprocessing: trigram index of every store catalogue
    indexes = [[trigrams(l["name"]) for l in cat] for cat in catalogs]
    item_grams = [trigrams(it["name"]) for it in basket]
    t1 = time.perf_counter(); t["index"] = t1 - t0

    # 1. product matching: N x M searches, each over C listings
    matched = [[best_match(g, indexes[s]) for s in range(len(catalogs))] for g in item_grams]
    t2 = time.perf_counter(); t["matching"] = t2 - t1

    # 2. price lookup
    price = [[None] * len(catalogs) for _ in basket]  # None = unavailable
    correct = 0
    for i, it in enumerate(basket):
        for s, cat in enumerate(catalogs):
            lst = cat[matched[i][s]]
            if lst["pid"] == it["pid"]:
                correct += 1
            if lst["available"]:
                price[i][s] = lst["price"]

    # 3. basket totals (available items only) and completeness
    totals = [sum(price[i][s] * basket[i]["qty"] for i in range(len(basket)) if price[i][s] is not None)
              for s in range(len(catalogs))]
    complete = [all(price[i][s] is not None for i in range(len(basket))) for s in range(len(catalogs))]

    # 4. cheapest complete basket
    complete_stores = [s for s in range(len(catalogs)) if complete[s]]
    best_store = min(complete_stores, key=lambda s: totals[s]) if complete_stores else None

    # 5. cheapest store per item
    cheapest = []
    for i in range(len(basket)):
        avail = [(price[i][s], s) for s in range(len(catalogs)) if price[i][s] is not None]
        cheapest.append(min(avail) if avail else None)

    # 6. smart split
    split_total, split_possible = 0.0, all(c is not None for c in cheapest)
    if split_possible:
        split_total = sum(cheapest[i][0] * basket[i]["qty"] for i in range(len(basket)))

    t3 = time.perf_counter(); t["compare"] = t3 - t2
    t["total"] = t3 - t0

    result = {
        "totals": totals, "complete": complete, "best_store": best_store,
        "split_total": split_total if split_possible else None,
        "saving": (totals[best_store] - split_total) if (best_store is not None and split_possible) else None,
        "accuracy": correct / (len(basket) * len(catalogs)),
    }
    return result, t


# ---------------------------------------------------------------------------------------
def cpu_info():
    model = platform.processor() or ""
    try:  # Linux: nicer model name
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return model or platform.machine(), os.cpu_count()


def main():
    ap = argparse.ArgumentParser(description="SmartBasket sequential benchmark")
    ap.add_argument("-n", "--items", type=int, default=100, help="N: items in the basket")
    ap.add_argument("-m", "--stores", type=int, default=4, help="M: number of stores (max 8)")
    ap.add_argument("-c", "--catalog", type=int, default=2000, help="C: listings per store")
    ap.add_argument("-r", "--repeats", type=int, default=5, help="number of timed repetitions")
    ap.add_argument("--seed", type=int, default=42, help="random seed (keep 42 for the whole group)")
    ap.add_argument("--csv", help="append one result row to this CSV file")
    a = ap.parse_args()
    a.stores = max(1, min(a.stores, len(STORE_NAMES)))

    model, cores = cpu_info()
    print(f"CPU: {model} | logical cores: {cores} | Python {platform.python_version()} | {platform.system()}")
    print(f"N={a.items} items, M={a.stores} stores, C={a.catalog} listings/store, repeats={a.repeats}, seed={a.seed}")

    basket, catalogs = generate_data(a.items, a.stores, a.catalog, a.seed)  # not timed
    n_items = len(basket)

    runs, stage = [], {"index": [], "matching": [], "compare": []}
    result = None
    for r in range(a.repeats):
        result, t = compare_basket(basket, catalogs)
        runs.append(t["total"])
        for k in stage:
            stage[k].append(t[k])
        print(f"  run {r + 1}: {t['total']:.4f} s")

    mean = statistics.mean(runs)
    sd = statistics.stdev(runs) if len(runs) > 1 else 0.0
    print(f"\nTotal time  mean={mean:.4f}s  min={min(runs):.4f}s  max={max(runs):.4f}s  std={sd:.4f}s")
    print("Average time per stage:")
    for k, label in (("index", "preprocessing (trigram index)"), ("matching", "1. product matching"),
                     ("compare", "2-6. price lookup / totals / split")):
        m = statistics.mean(stage[k])
        print(f"  {label:<36} {m:.4f}s  ({100 * m / mean:5.1f}%)")

    print(f"\nMatching accuracy: {100 * result['accuracy']:.2f}%")
    for s in range(a.stores):
        tag = "complete" if result["complete"][s] else "INCOMPLETE"
        print(f"  {STORE_NAMES[s]:<10} total = {result['totals'][s]:9.2f} SAR  ({tag})")
    if result["best_store"] is not None:
        print(f"Cheapest complete basket: {STORE_NAMES[result['best_store']]}")
    if result["split_total"] is not None:
        print(f"Smart split total: {result['split_total']:.2f} SAR"
              + (f"  (saving {result['saving']:.2f} SAR)" if result["saving"] is not None else ""))

    if a.csv:
        new = not os.path.exists(a.csv)
        with open(a.csv, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["cpu_model", "logical_cores", "N", "M", "C", "repeats",
                            "mean_s", "min_s", "std_s", "index_s", "matching_s", "compare_s", "accuracy"])
            w.writerow([model, cores, n_items, a.stores, a.catalog, a.repeats,
                        f"{mean:.4f}", f"{min(runs):.4f}", f"{sd:.4f}",
                        f"{statistics.mean(stage['index']):.4f}", f"{statistics.mean(stage['matching']):.4f}",
                        f"{statistics.mean(stage['compare']):.4f}", f"{result['accuracy']:.4f}"])
        print(f"\nResult row appended to {a.csv}")


if __name__ == "__main__":
    main()
