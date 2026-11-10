#!/usr/bin/env python3
"""Clean a google-maps-scraper results.csv into a scored Cytd lead file.

Usage: python3 scripts/cytd-clean.py RESULTS_CSV OUTPUT_CSV --queries QUERIES_TXT --niche NICHE
           --metro METRO --date YYYY-MM-DD [--target-leads N] [--earlier FILE ...]

Rows are read in search-query order. Zips are added until the target of
qualified leads is reached. Run the scraper with "query #!#query" lines so
input_id holds the search query.
"""
import argparse
import csv
import importlib.util
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

spec = importlib.util.spec_from_file_location("gmaps_export", Path(__file__).with_name("gmaps-export.py"))
gx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gx)

CHAINS = [
    "one hour", "mr. rooter", "mr rooter", "benjamin franklin", "roto-rooter", "roto rooter",
    "mister sparky", "service experts", "the joint", "upstream", "aspen dental", "western dental",
    "heartland dental", "orangetheory", "f45", "anytime fitness", "planet fitness", "crunch",
    "club pilates", "pure barre", "burn boot camp", "snap fitness", "la fitness", "gold's gym",
    "golds gym", "rescue rooter",
]
CHAIN_WORDS = re.compile(r"\b(ars|ati|athletico)\b", re.I)
BIG_ORGS = re.compile(
    r"hospital|health system|medical center|bank of america|\bchase\b|wells fargo|citibank|"
    r"\bpnc\b|truist|capital one|u\.?s\.? bank|regions bank|td bank", re.I)
SOCIAL = ("facebook.", "instagram.", "linkedin.", "twitter.", "x.com", "tiktok.", "youtube.",
          "yelp.", "nextdoor.", "pinterest.", "linktr.ee", "business.site", "google.com",
          "angi.com", "homeadvisor.", "thumbtack.", "bbb.org", "yellowpages.", "mapquest.")
BROKERAGE = ("zillow.", "realtor.com", "redfin.", "kw.com", "remax.", "compass.com",
             "coldwellbanker.", "century21.", "exprealty.", "bhhs", "sothebys", "trulia.")
CHAIN_DOMAINS = ("onehourheatandair", "mrrooter", "bfranklinplumbing", "roto-rooter", "mistersparky",
                 "ars.com", "serviceexperts", "thejoint", "aspendental", "westerndental",
                 "heartland", "orangetheory", "f45training", "anytimefitness", "planetfitness",
                 "crunch.com", "clubpilates", "purebarre", "bootcamp", "snapfitness",
                 "lafitness", "goldsgym")
LOCATOR_PATH = re.compile(r"/(locations?|find-a-\w+|store-locator|branches|franchise)(/|$)", re.I)

COLUMNS = ["Business name", "Niche", "Category", "Search query", "Rating", "Reviews", "Phone",
           "Website", "Address line 1", "City", "State", "Zip", "Metro", "Google Maps URL",
           "Emails", "Lead score", "Scraped date", "Batch ID", "Notes"]


def root_domain(website):
    host = urlparse(website if "//" in website else "//" + website).netloc.lower().split(":")[0]
    host = re.sub(r"^www\d?\.", "", host)
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def phone_digits(phone):
    return re.sub(r"\D", "", phone)[-10:]


def drop_reason(row):
    phone, site = row.get("phone", ""), row.get("website", "").strip()
    if not phone or not site:
        return "no phone or website"
    if "closed" in row.get("status", "").lower():
        return "closed"
    host, parsed = root_domain(site), urlparse(site if "//" in site else "//" + site)
    if any(s in host + "/" for s in SOCIAL) or any(b in host for b in BROKERAGE):
        return "social or brokerage site"
    if any(c in host for c in CHAIN_DOMAINS) or LOCATOR_PATH.search(parsed.path or ""):
        return "franchise or locator page"
    name = row.get("title", "")
    if any(c in name.lower() for c in CHAINS) or CHAIN_WORDS.search(name) or BIG_ORGS.search(name):
        return "chain or big org"
    try:
        rating, reviews = float(row.get("review_rating") or 0), int(float(row.get("review_count") or 0))
    except ValueError:
        return "low rating"
    if rating < 4.0 or reviews < 5:
        return "low rating"
    return ""


def score(row):
    rating, reviews = float(row["review_rating"]), int(float(row["review_count"]))
    if rating >= 4.5 and reviews >= 50:
        return "A"
    return "B" if reviews >= 20 else "C"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--queries", required=True)
    ap.add_argument("--niche", required=True)
    ap.add_argument("--metro", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--target-leads", type=int, default=50)
    ap.add_argument("--earlier", nargs="*", default=[])
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    queries = [line.split("#!#")[-1].strip() for line in open(args.queries, encoding="utf-8") if line.strip()]
    batch = f"{args.date}-{re.sub(r'[^a-z0-9]+', '-', args.metro.lower())}-{re.sub(r'[^a-z0-9]+', '-', args.niche.lower())}"

    seen_phone, seen_domain, seen_name = set(), set(), set()
    for path in args.earlier:
        for r in csv.DictReader(open(path, encoding="utf-8")):
            seen_phone.add(phone_digits(r.get("Phone", "")))
            if r.get("Website"):
                seen_domain.add(root_domain(r["Website"]))

    drops, kept, last_query = {}, [], None
    for query in queries:
        batch_rows = sorted((r for r in rows if r["input_id"] == query),
                            key=lambda r: -float(r.get("review_count") or 0))
        for row in batch_rows:
            reason = drop_reason(row)
            if not reason:
                addr = json.loads(row.get("complete_address") or "{}")
                name_key = (row["title"].strip().lower(), addr.get("postal_code", ""))
                p, d = phone_digits(row["phone"]), root_domain(row["website"])
                if p in seen_phone or d in seen_domain or name_key in seen_name:
                    reason = "duplicate"
                else:
                    seen_phone.add(p), seen_domain.add(d), seen_name.add(name_key)
            if reason:
                drops[reason] = drops.get(reason, 0) + 1
            else:
                kept.append(row)
        last_query = query
        if len(kept) >= args.target_leads:
            break

    addresses = [gx.split_address(r.get("complete_address", "")) for r in kept]
    missing = [i for i, a in enumerate(addresses) if not any(a)]
    points = gx._zip_points() if missing else []
    with ThreadPoolExecutor(max_workers=16) as pool:
        streets = list(pool.map(gx.find_street, [kept[i]["website"] for i in missing]))
    notes = [""] * len(kept)
    for i, street in zip(missing, streets):
        place = gx.nearest_zip(points, float(kept[i]["latitude"]), float(kept[i]["longitude"]))
        addresses[i] = [street, *place]
        notes[i] = "No address on Google. City, State, Zip from map pin."

    order = sorted(range(len(kept)), key=lambda i: (score(kept[i]), -int(float(kept[i]["review_count"]))))
    counts = {"A": 0, "B": 0, "C": 0}
    with open(args.target, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for i in order:
            r, a = kept[i], addresses[i]
            s = score(r)
            counts[s] += 1
            w.writerow([r["title"], args.niche, r["category"], r["input_id"], f"{float(r['review_rating']):g}",
                        r["review_count"], gx.clean_phone(r["phone"]), r["website"], *a, args.metro,
                        r["link"], r.get("emails", ""), s, args.date, batch, notes[i]])
    print(json.dumps({"queries_in_file": len(queries), "queries_used": queries.index(last_query) + 1,
                      "last_query": last_query, "raw_rows": len(rows), "kept": len(kept),
                      "scores": counts, "dropped": drops}, indent=2))


if __name__ == "__main__":
    main()
