#!/usr/bin/env python3
"""Turn a google-maps-scraper results.csv into a clean leads CSV.

Usage: python3 scripts/gmaps-export.py RESULTS_CSV OUTPUT_CSV

Rows Google lists without an address get City, State and Zip from the nearest
ZIP code to their map pin. Address 1 is looked up on the business website and
left blank when the site does not publish a street address.
Needs: pip install zipcodes
"""
import csv
import json
import math
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import zipcodes

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}

HEADER = ["Business", "Category", "Rating", "Reviews", "Phone", "Website",
          "Address 1", "City", "State", "Zip", "Google Maps"]


def _zip_points():
    return [(float(z["lat"]), float(z["long"]), z) for z in zipcodes.list_all()
            if z["zip_code_type"] == "STANDARD" and z["lat"] and z["long"]]


def nearest_zip(points, lat, lng):
    lng_scale = math.cos(math.radians(lat))
    best = min(points, key=lambda p: (p[0] - lat) ** 2 + ((p[1] - lng) * lng_scale) ** 2)
    z = best[2]
    return [z["city"].title(), z["state"], z["zip_code"]]


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.read(400_000).decode("utf-8", "ignore")
    except Exception:
        return ""


def street_from_html(html):
    for block in re.findall(r"<script[^>]+ld\+json[^>]*>(.*?)</script>", html, re.S | re.I):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                address = node.get("address")
                if isinstance(address, dict):
                    street = str(address.get("streetAddress", "")).strip()
                    if re.search(r"\d", street):
                        return street
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return ""


def find_street(website):
    if not website:
        return ""
    for path in ("", "/contact", "/contact-us"):
        street = street_from_html(fetch(urljoin(website, path)))
        if street:
            return street
    return ""


def clean_phone(raw):
    return raw[2:].strip() if raw.startswith("+1 ") else raw


def split_address(raw):
    try:
        parts = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parts = {}
    state = parts.get("state", "")
    return [parts.get("street", ""), parts.get("city", ""),
            STATES.get(state, state), parts.get("postal_code", "")]


def main(source, target):
    with open(source, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    seen = set()
    unique = []
    for row in rows:
        key = row.get("place_id") or row.get("title")
        if key not in seen:
            seen.add(key)
            unique.append(row)
    unique.sort(key=lambda r: -float(r.get("review_count") or 0))

    addresses = [split_address(r.get("complete_address", "")) for r in unique]
    missing = [i for i, a in enumerate(addresses) if not any(a)]
    points = _zip_points() if missing else []
    with ThreadPoolExecutor(max_workers=16) as pool:
        streets = list(pool.map(find_street, [unique[i].get("website", "") for i in missing]))
    for i, street in zip(missing, streets):
        row = unique[i]
        try:
            place = nearest_zip(points, float(row["latitude"]), float(row["longitude"]))
        except (KeyError, ValueError):
            place = ["", "", ""]
        addresses[i] = [street, *place]

    with open(target, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r, address in zip(unique, addresses):
            rating = r.get("review_rating", "")
            writer.writerow([
                r.get("title", ""), r.get("category", ""),
                f"{float(rating):g}" if rating else "", r.get("review_count", ""),
                clean_phone(r.get("phone", "")), r.get("website", ""),
                *address,
                r.get("link", ""),
            ])
    print(f"{len(unique)} leads written to {target}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
