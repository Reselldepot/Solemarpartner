"""
Schritt 3: Trennt Einzelläden von bekannten Ketten/Franchises.

Zwei Ausgabe-Dateien:
  - leads_ready.csv        alles, was NICHT auf der Ketten-Blockliste
                            steht - unabhängig davon, ob eine E-Mail
                            gefunden wurde oder der Name mehrfach im
                            Datensatz auftaucht. Kein manueller
                            Zwischenschritt mehr.
  - excluded_chains.csv    Treffer aus der bekannten Ketten-Blockliste
                            (config.CHAIN_BLOCKLIST)

WICHTIG: Die automatische Ketten-Erkennung basiert ausschließlich auf
der Namens-Blockliste in config.py. Sie ist nicht vollständig - unbekannte
Filialketten, die nicht in der Liste stehen, rutschen mit durch. Die
Blockliste bei Bedarf in config.py ergänzen.

Zeilen ohne E-Mail landen zwar in leads_ready.csv (damit nichts verloren
geht), werden aber von mailchimp_import.py automatisch übersprungen,
da Mailchimp ohne E-Mail-Adresse keinen Kontakt anlegen kann.
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

    ready, excluded = [], []
    for row in rows:
        if is_known_chain(row["name"]):
            row["exclude_reason"] = "bekannte Kette (Blockliste)"
            excluded.append(row)
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
    write(config.EXCLUDED_CHAINS_CSV, excluded, "exclude_reason")

    with_email = sum(1 for r in ready if r["email"])
    without_email = len(ready) - with_email

    print(f"Bereit für Mailchimp (nicht auf Ketten-Blockliste): {len(ready):4d}  -> {config.READY_CSV}")
    print(f"  davon mit E-Mail (werden importiert):             {with_email:4d}")
    print(f"  davon ohne E-Mail (werden übersprungen):          {without_email:4d}")
    print(f"Ausgeschlossene Ketten:                              {len(excluded):4d}  -> {config.EXCLUDED_CHAINS_CSV}")


if __name__ == "__main__":
    main()
