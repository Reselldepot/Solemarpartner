"""
Schritt 1: Findet Friseurläden, Beauty-Salons und Tattoo-Studios im
30-km-Umkreis von Freudenstadt über die Overpass-API (OpenStreetMap).

Warum OpenStreetMap statt Google Maps / Gelbe Seiten scrapen?
- Freie, offen lizenzierte Daten (ODbL) -> kein Verstoß gegen Google-
  Nutzungsbedingungen, keine Anti-Bot-Blockaden nötig.
- Liefert bereits Adresse, Telefon, Website und teils E-Mail als Tags.

Die Overpass-API liefert nicht jeden kleinen Salon (OSM-Abdeckung ist in
Kleinstädten lückenhaft) -> das Ergebnis ist eine gute Grundliste, aber
kein Anspruch auf Vollständigkeit. Ergänzung von Hand (z. B. via lokalem
Branchenverzeichnis) sinnvoll.
"""
import csv
import math
import sys
import time

import requests

sys.path.insert(0, ".")
import config  # noqa: E402

# Mehrere Spiegelserver probieren (overpass-api.de blockt manche Cloud-/
# Rechenzentrums-IPs mit HTTP 406; kumi.systems als zuverlässige Alternative).
OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_query():
    clauses = []
    for label, tag_pairs in config.OSM_CATEGORIES.items():
        for key, value in tag_pairs:
            for kind in ("node", "way", "relation"):
                clauses.append(
                    f'{kind}["{key}"="{value}"](around:{config.RADIUS_M},'
                    f"{config.ORIGIN_LAT},{config.ORIGIN_LON});"
                )
    body = "\n  ".join(clauses)
    return f"""
[out:json][timeout:90];
(
  {body}
)
;
out center tags;
"""


def category_for_tags(tags):
    for label, tag_pairs in config.OSM_CATEGORIES.items():
        for key, value in tag_pairs:
            if tags.get(key) == value:
                return label
    return "unbekannt"


def extract_row(element):
    tags = element.get("tags", {})
    if element["type"] == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        center = element.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None

    dist_km = haversine_km(config.ORIGIN_LAT, config.ORIGIN_LON, lat, lon)
    if dist_km > config.RADIUS_M / 1000:
        return None  # around-Filter ist für "way"/"relation" nur ungefähr

    name = tags.get("name", "").strip()
    if not name:
        return None

    street = tags.get("addr:street", "")
    housenumber = tags.get("addr:housenumber", "")
    postcode = tags.get("addr:postcode", "")
    city = tags.get("addr:city", "")
    address = " ".join(p for p in [street, housenumber] if p).strip()

    email = tags.get("contact:email") or tags.get("email") or ""
    website = tags.get("contact:website") or tags.get("website") or ""
    phone = tags.get("contact:phone") or tags.get("phone") or ""

    return {
        "osm_type": element["type"],
        "osm_id": element["id"],
        "category": category_for_tags(tags),
        "name": name,
        "street_address": address,
        "postcode": postcode,
        "city": city,
        "phone": phone,
        "website": website,
        "email": email,
        "lat": lat,
        "lon": lon,
        "distance_km": round(dist_km, 1),
    }


def main():
    print(f"Frage Overpass-API ab (Radius {config.RADIUS_M/1000:.0f} km um "
          f"Freudenstadt)...")
    query = build_query()

    resp = None
    last_error = None
    for url in OVERPASS_URLS:
        try:
            print(f"  versuche {url} ...")
            resp = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": config.USER_AGENT},
                timeout=100,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"    fehlgeschlagen ({exc}), versuche nächsten Spiegelserver...")
            resp = None
            continue

    if resp is None:
        raise RuntimeError(
            f"Alle Overpass-Spiegelserver fehlgeschlagen. Letzter Fehler: {last_error}"
        )

    elements = resp.json().get("elements", [])
    print(f"{len(elements)} Roh-Treffer von OSM erhalten.")

    rows = []
    seen = set()
    for el in elements:
        row = extract_row(el)
        if not row:
            continue
        dedup_key = (row["name"].lower(), round(row["lat"], 4), round(row["lon"], 4))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        rows.append(row)

    rows.sort(key=lambda r: (r["category"], r["distance_km"]))

    import os
    os.makedirs(config.DATA_DIR, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "osm_type", "osm_id", "category", "name", "street_address",
        "postcode", "city", "phone", "website", "email", "lat", "lon",
        "distance_km",
    ]
    with open(config.RAW_LEADS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} eindeutige Betriebe gespeichert -> {config.RAW_LEADS_CSV}")
    with_email = sum(1 for r in rows if r["email"])
    with_site = sum(1 for r in rows if r["website"])
    print(f"  davon mit E-Mail direkt aus OSM: {with_email}")
    print(f"  davon mit Website (für Schritt 2 - E-Mail-Anreicherung): {with_site}")


if __name__ == "__main__":
    main()
