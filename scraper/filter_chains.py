"""
Schritt 3: Trennt Einzelläden von (vermuteten) Ketten/Franchises.

Drei Ausgabe-Dateien:
  - leads_ready.csv        eindeutig aussehende Einzelläden mit E-Mail
  - needs_review.csv       Namen, die mehrfach im Datensatz vorkommen
                            (mögliche Filialkette) ODER ohne E-Mail
  - excluded_chains.csv    Treffer aus der bekannten Ketten-Blockliste

WICHTIG: Automatische Ketten-Erkennung ist nie perfekt. Bitte
needs_review.csv vor dem Import/Anschreiben kurz von Hand durchsehen -
manche Namen (z. B. "Haarstudio") kommen bei unabhängigen Läden einfach
öfter zufällig vor.
"""
import csv
import re
import sys

sys.path.insert(0, ".")
import config  # noqa: E402


def normalize_name(name: str) -> str:
    n = name.lower().strip()
    for suffix in config.LEGAL_SUFFIXES:
        n = n.replace(suffix, "")
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def is_known_chain(name: str) -> bool:
    n = name.lower()
    return any(chain in n for chain in config.CHAIN_BLOCKLIST)


def main():
    with open(config.ENRICHED_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        row["normalized_name"] = normalize_name(row["name"])

    name_counts = {}
    for row in rows:
        name_counts[row["normalized_name"]] = name_counts.get(row["normalized_name"], 0) + 1

    ready, review, excluded = [], [], []
    for row in rows:
        if is_known_chain(row["name"]):
            row["exclude_reason"] = "bekannte Kette (Blockliste)"
            excluded.append(row)
        elif name_counts[row["normalized_name"]] > 1:
            row["review_reason"] = "Name mehrfach im Datensatz - evtl. Filialkette"
            review.append(row)
        elif not row["email"]:
            row["review_reason"] = "keine E-Mail gefunden - manuell nachschlagen?"
            review.append(row)
        else:
            ready.append(row)

    base_fieldnames = list(rows[0].keys()) if rows else [
        "osm_type", "osm_id", "category", "name", "street_address",
        "postcode", "city", "phone", "website", "email", "lat", "lon",
        "distance_km", "normalized_name",
    ]

    def write(path, data, extra_field=None):
        if not data:
            fieldnames = base_fieldnames + ([extra_field] if extra_field else [])
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
            return
        fieldnames = list(data[0].keys())
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    write(config.READY_CSV, ready)
    write(config.NEEDS_REVIEW_CSV, review, "review_reason")
    write(config.EXCLUDED_CHAINS_CSV, excluded, "exclude_reason")

    print(f"Einzelläden mit E-Mail, bereit:  {len(ready):4d}  -> {config.READY_CSV}")
    print(f"Zur manuellen Prüfung:           {len(review):4d}  -> {config.NEEDS_REVIEW_CSV}")
    print(f"Ausgeschlossene Ketten:          {len(excluded):4d}  -> {config.EXCLUDED_CHAINS_CSV}")


if __name__ == "__main__":
    main()
