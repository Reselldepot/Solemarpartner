"""
Schritt 2: Ergänzt fehlende E-Mail-Adressen, indem die angegebene Website
jedes Betriebs besucht wird - und zwar möglichst gründlich, bevor ein
Betrieb ohne E-Mail bleibt:

  1. Startseite selbst nach mailto:-Link / E-Mail-Muster durchsuchen.
  2. Auf der Startseite den TATSÄCHLICH verlinkten Impressum- bzw.
     Kontakt-Link suchen (Link-Text oder href enthält "impressum" /
     "kontakt" / "contact" / "imprint") und dieser Seite folgen - das
     trifft die echte URL auch dann, wenn sie z.B. "/unternehmen/impressum"
     oder "/pages/imprint" statt "/impressum" heißt.
  3. Erst wenn das nichts findet, eine Liste häufiger Pfade raten
     (Rückfallebene für Seiten ohne auffindbaren Link, z.B. Impressum
     nur im Menü, das per JavaScript nachgeladen wird).

Ziel: möglichst wenige Betriebe bleiben ohne E-Mail übrig. Wer trotzdem
keine hat, hat schlicht keine öffentlich verlinkte Website mit
auffindbarer Adresse (z.B. nur eine Facebook-Seite als "Website"
hinterlegt) - dafür gibt es keine Abkürzung, ohne Adresshandel/Login-
Umgehung zu betreiben.

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

# Rückfallebene, falls auf der Startseite kein Impressum-/Kontakt-Link
# gefunden wird (z.B. weil das Menü nur per JavaScript existiert).
FALLBACK_PATHS = [
    "/impressum", "/impressum/", "/impressum.html", "/de/impressum",
    "/unternehmen/impressum", "/pages/impressum", "/rechtliches/impressum",
    "/kontakt", "/kontakt/", "/contact", "/contact-us", "/pages/contact",
    "/imprint", "/imprint/", "/legal-notice", "/pages/imprint",
]

# Keywords, nach denen echte Impressum-/Kontakt-Links auf der Startseite
# gesucht werden (in Link-Text ODER href, klein geschrieben).
IMPRESSUM_KEYWORDS = ("impressum", "imprint", "legal notice", "rechtliches")
KONTAKT_KEYWORDS = ("kontakt", "contact")


def looks_like_junk(email: str) -> bool:
    e = email.lower()
    return any(p in e for p in JUNK_PATTERNS)


def extract_email_from_html(html: str):
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


def find_linked_page(html: str, base_url: str, keywords):
    """Sucht auf einer Seite einen Link, dessen sichtbarer Text ODER href
    eines der Keywords enthält, und gibt die absolute URL zurück - aber
    nur auf derselben Domain (kein Verfolgen von z.B. Social-Media-Links,
    die zufällig "Kontakt" im Linktext haben)."""
    same_domain = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True).lower()
        haystack = f"{text} {href.lower()}"
        if any(kw in haystack for kw in keywords):
            if href.lower().startswith(("mailto:", "tel:", "javascript:")):
                continue
            candidate = urljoin(base_url, href)
            if urlparse(candidate).netloc == same_domain:
                return candidate
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


def fetch_and_wait(url: str):
    html = try_fetch(url)
    time.sleep(config.DELAY_BETWEEN_REQUESTS_S)
    return html


def discover_email(website: str):
    if not website:
        return None
    if not website.startswith("http"):
        website = "https://" + website
    parsed = urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"

    visited = set()

    def check(url):
        if url in visited:
            return None
        visited.add(url)
        html = fetch_and_wait(url)
        if not html:
            return None
        email = extract_email_from_html(html)
        return (email, html)

    # 1) Startseite direkt
    result = check(base)
    if result is None:
        homepage_html = None
    else:
        email, homepage_html = result
        if email:
            return email

    # 2) Echten Impressum-/Kontakt-Link auf der Startseite finden und folgen
    if homepage_html:
        for keywords in (IMPRESSUM_KEYWORDS, KONTAKT_KEYWORDS):
            link = find_linked_page(homepage_html, base, keywords)
            if not link or link in visited:
                continue
            result = check(link)
            if result and result[0]:
                return result[0]

    # 3) Rückfallebene: häufige Pfade raten
    for path in FALLBACK_PATHS:
        url = urljoin(base, path)
        if url in visited:
            continue
        result = check(url)
        if result and result[0]:
            return result[0]

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

    still_missing = sum(1 for r in rows if not r["email"])
    print(f"\nFertig. {found} neue E-Mail-Adressen gefunden.")
    print(f"{still_missing} Betriebe insgesamt weiterhin ohne E-Mail "
          f"(keine Website hinterlegt, oder auf der Website keine "
          f"öffentliche Adresse auffindbar).")
    print(f"Gespeichert -> {config.ENRICHED_CSV}")


if __name__ == "__main__":
    main()
