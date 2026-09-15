"""
Schritt 2: Ergänzt fehlende E-Mail-Adressen, indem die angegebene Website
jedes Betriebs besucht wird (Startseite, dann /impressum, /kontakt, /contact).

Warum das rechtlich die sauberste Quelle ist:
In Deutschland sind Gewerbetreibende per Impressumspflicht (§5 DDG,
ehem. §5 TMG) verpflichtet, eine Kontakt-E-Mail auf der eigenen Website
zu veröffentlichen. Wir lesen also genau die Adresse, die der Betrieb
selbst für Geschäftsanfragen bestimmt hat - keine private Adresse, kein
Adresshandel, kein Umgehen von Login-/Bezahlschranken.

Das Skript ist bewusst höflich: eigener User-Agent mit Kontaktangabe,
Timeout, Pause zwischen Requests, respektiert robots.txt nicht aktiv
geprüft (kleine Website-Anzahl) - bei Bedarf ergänzen.
"""
import csv
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, ".")
import config  # noqa: E402

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Adressen, die typischerweise keine echten Kontaktadressen sind
JUNK_PATTERNS = (
    "sentry", "wixpress", "example.com", "no-reply", "noreply@",
    "schema.org", ".png", ".jpg", ".svg",
)

CANDIDATE_PATHS = ["", "/impressum", "/kontakt", "/contact", "/imprint"]


def looks_like_junk(email: str) -> bool:
    e = email.lower()
    return any(p in e for p in JUNK_PATTERNS)


def find_email_on_page(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")

    # 1) mailto:-Links haben Vorrang, sind am zuverlässigsten
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr and not looks_like_junk(addr):
                return addr

    # 2) sonst Freitext nach E-Mail-Mustern durchsuchen
    text = soup.get_text(" ", strip=True)
    for match in EMAIL_RE.findall(text):
        if not looks_like_junk(match):
            return match
    return None


def try_fetch(url: str):
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT_S,
        )
        if resp.status_code == 200:
            return resp.text
    except requests.RequestException:
        return None
    return None


def discover_email(website: str):
    if not website:
        return None
    if not website.startswith("http"):
        website = "https://" + website
    parsed = urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in CANDIDATE_PATHS:
        url = urljoin(base, path)
        html = try_fetch(url)
        time.sleep(config.DELAY_BETWEEN_REQUESTS_S)
        if not html:
            continue
        email = find_email_on_page(html, url)
        if email:
            return email
    return None


def main():
    with open(config.RAW_LEADS_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total_to_check = sum(1 for r in rows if not r["email"] and r["website"])
    print(f"{len(rows)} Betriebe geladen, {total_to_check} ohne E-Mail aber mit "
          f"Website werden jetzt geprüft (das kann dauern)...")

    checked = 0
    found = 0
    for row in rows:
        if row["email"] or not row["website"]:
            continue
        checked += 1
        email = discover_email(row["website"])
        if email:
            row["email"] = email
            found += 1
        print(f"  [{checked}/{total_to_check}] {row['name'][:40]:40s} "
              f"-> {email or 'nichts gefunden'}")

    with open(config.ENRICHED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nFertig. {found} neue E-Mail-Adressen gefunden.")
    print(f"Gespeichert -> {config.ENRICHED_CSV}")


if __name__ == "__main__":
    main()
