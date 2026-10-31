#!/usr/bin/env python3
"""Turn a google-maps-scraper results.csv into a clean leads CSV.

Usage: python3 scripts/gmaps-export.py RESULTS_CSV OUTPUT_CSV
"""
import csv
import json
import sys

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

    with open(target, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r in unique:
            rating = r.get("review_rating", "")
            writer.writerow([
                r.get("title", ""), r.get("category", ""),
                f"{float(rating):g}" if rating else "", r.get("review_count", ""),
                r.get("phone", ""), r.get("website", ""),
                *split_address(r.get("complete_address", "")),
                r.get("link", ""),
            ])
    print(f"{len(unique)} leads written to {target}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
