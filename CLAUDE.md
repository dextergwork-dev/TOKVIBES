# TOKVIBES

## Communication style: Dale Carnegie

Apply to every daily update and any message to editors, strategists, or clients. Start each message with an acknowledgment written in the Dale Carnegie style.

How to write the acknowledgment:
- Open with honest, specific appreciation for something the person did. Name the work, not just "great job".
- Use the person's name.
- Show you see their side. Say what the update means for them.
- Never criticize or blame. Frame problems as next steps or questions.
- Keep it to one or two sentences, then give the update.

Per audience:
- Editors: thank them for a specific edit or turnaround. Tell them what the update frees up for them.
- Strategists: credit a specific idea or call. Tell them how the update supports their plan.
- Clients: thank them for their trust or feedback. Lead with the result they care about.

Keep the tone warm and sincere. No flattery that is not true. No em dashes.

## Google Maps scrapes

After a google-maps-scraper crawl, build the leads file with:

    python3 scripts/gmaps-export.py <results.csv> leads/<name>.csv

It dedupes, sorts by review count, and splits the address into Address 1, City, State (2-letter) and Zip with no country, and drops the +1 from phone numbers. For businesses Google lists without an address, it fills City, State and Zip from the nearest ZIP to the map pin, and looks for Address 1 on the business website (blank if none). Needs `pip install zipcodes`. Keep lead files in `leads/` (gitignored).

Each ZIP list request gets its own new leads file. Never merge it into an earlier file. Skip ZIPs already scraped only when the user says so.

## Cytd lead runs

Write queries as `hvac contractor 75001 #!#hvac contractor 75001` so input_id holds the search query. After the crawl, run `python3 scripts/cytd-clean.py <results.csv> leads/<date>_<metro>_<niche>.csv --queries <queries.txt> --niche ... --metro ... --date ... --target-leads 50 [--earlier <lead files>]`. It filters, scores A/B/C, dedupes, and stops adding zips once the target is hit. Keep the raw results.csv beside it.
