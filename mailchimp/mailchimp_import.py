"""
Importiert data/3_leads_ready.csv als Mitglieder in eine Mailchimp-Audience.

****************************************************************************
WICHTIGER HINWEIS, BITTE VOR DER NUTZUNG LESEN:

Mailchimps Nutzungsbedingungen (Acceptable Use Policy) verbieten das
Hochladen von E-Mail-Listen, die durch Scraping, Kauf oder ohne
nachweisbare Einwilligung der Empfänger entstanden sind. Wer das trotzdem
tut, riskiert die sofortige Sperrung des gesamten Mailchimp-Accounts -
unabhängig davon, ob nur ein Teil der Liste "problematisch" ist.

Zusätzlich gilt in Deutschland: Werbung per E-Mail ohne vorherige
ausdrückliche Einwilligung ist nach §7 UWG grundsätzlich unzulässig
("Kaltakquise per E-Mail") und kann zu kostenpflichtigen Abmahnungen
führen, auch im B2B-Bereich.

DESHALB ist der Status für neue Kontakte hier standardmäßig auf
"pending" gesetzt (Mailchimps Double-Opt-in): Der Betrieb bekommt von
Mailchimp automatisch eine Bestätigungs-Mail und taucht erst nach Klick
als "subscribed" in der Liste auf. Das ist die einzige Variante, die mit
Mailchimps Regeln zuverlässig vereinbar ist.

EMPFOHLENER ABLAUF (siehe auch README.md):
  1. Erstkontakt NICHT über Mailchimp, sondern über
     outreach/send_outreach.py (persönliche Einzel-Mail an die im
     Impressum veröffentlichte Geschäftsadresse, mit Link zur
     Partnerprogramm-Anmeldeseite).
  2. Erst wer sich dort aktiv anmeldet, kommt sauber (mit Einwilligung)
     in Mailchimp - z.B. automatisch per Mailchimp-Anmeldeformular auf
     der Partnerseite, oder manuell über dieses Skript mit
     --status subscribed NUR für Leute, die nachweislich zugestimmt haben.

Das Ausführen mit --status subscribed für die rohe Scraper-Liste wird
nicht empfohlen und liegt in der Verantwortung der nutzenden Person.
****************************************************************************
"""
import argparse
import csv
import hashlib
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, ".")
import config  # noqa: E402

load_dotenv()

CATEGORY_TAGS = {
    "friseur": "Partner-Lead: Friseur",
    "beauty": "Partner-Lead: Beauty",
    "tattoo": "Partner-Lead: Tattoo",
}


def mailchimp_request(method, path, server, api_key, **kwargs):
    url = f"https://{server}.api.mailchimp.com/3.0{path}"
    try:
        return requests.request(
            method, url, auth=("anystring", api_key), timeout=15, **kwargs
        )
    except requests.exceptions.RequestException as exc:
        # Am häufigsten die Ursache: MAILCHIMP_SERVER_PREFIX passt nicht
        # zum API-Key (z.B. Key endet auf "-us21", Prefix ist aber "us6")
        # -> falsche Subdomain -> DNS-/Verbindungsfehler statt HTTP-Fehler.
        sys.exit(
            f"Netzwerkfehler beim Aufruf von {url}: {exc}\n"
            f"Häufigste Ursache: MAILCHIMP_SERVER_PREFIX passt nicht zum "
            f"API-Key. Der Server-Prefix ist genau der Teil NACH dem "
            f"letzten Bindestrich im API-Key (z.B. Key endet auf "
            f"'...-us21' -> Prefix ist 'us21')."
        )


def verify_credentials(server, api_key, audience_id):
    """Prüft VOR dem eigentlichen Import in einem einzigen Request, ob
    API-Key, Server-Prefix und Audience-ID zusammenpassen. Ohne diese
    Prüfung sieht man bei falschen Zugangsdaten nur "18 versucht, 0
    angekommen" ohne zu wissen warum - das hier gibt eine klare Antwort,
    bevor überhaupt ein Kontakt verarbeitet wird."""
    resp = mailchimp_request(
        "GET", f"/lists/{audience_id}?fields=id,name,stats.member_count",
        server, api_key,
    )
    if resp.status_code == 200:
        info = resp.json()
        print(f"Mailchimp-Verbindung OK -> Audience \"{info.get('name')}\" "
              f"({info.get('stats', {}).get('member_count', '?')} bestehende Mitglieder)\n")
        return
    if resp.status_code == 401:
        sys.exit(
            "Fehler: Mailchimp lehnt den API-Key ab (401 Unauthorized).\n"
            "Prüfen: MAILCHIMP_API_KEY korrekt kopiert (keine Leerzeichen/"
            "Zeilenumbruch)? Und passt MAILCHIMP_SERVER_PREFIX zum Teil "
            "nach dem letzten Bindestrich im Key (z.B. '...-us21' -> 'us21')?"
        )
    if resp.status_code == 404:
        sys.exit(
            f"Fehler: Audience/Liste mit ID '{audience_id}' wurde nicht "
            f"gefunden (404). MAILCHIMP_AUDIENCE_ID prüfen: Mailchimp -> "
            f"Audience -> Settings -> Audience name and defaults -> "
            f"'Audience ID'."
        )
    sys.exit(f"Fehler beim Verbindungstest: HTTP {resp.status_code} - {resp.text[:300]}")


ACTIVE_STATUSES = ("subscribed", "pending")


def existing_status(server, api_key, audience_id, subscriber_hash):
    """Fragt Mailchimp selbst nach dem Status eines Kontakts - statt uns
    auf eine lokale Log-Datei zu verlassen. Das ist wichtig, sobald die
    Pipeline z.B. als Render Cron Job läuft: dort startet jeder Lauf mit
    einem frischen, leeren Dateisystem (kein Disk-Support für Cron Jobs).

    WICHTIG (Bugfix): Mailchimp "löscht" Kontakte über die Oberfläche
    standardmäßig nicht wirklich, sondern archiviert sie nur. Ein
    archivierter Kontakt liefert bei GET weiterhin HTTP 200, taucht aber
    NICHT mehr in der normalen Kontakt-Ansicht im Dashboard auf. Ein
    reines "existiert der Datensatz überhaupt?" (nur HTTP-Status prüfen)
    hat solche Kontakte fälschlich als "schon vorhanden" übersprungen,
    obwohl sie im Dashboard gar nicht sichtbar waren. Deshalb jetzt: den
    tatsächlichen 'status' auswerten und zurückgeben (oder None, wenn
    nicht gefunden)."""
    resp = mailchimp_request(
        "GET", f"/lists/{audience_id}/members/{subscriber_hash}?fields=status",
        server, api_key,
    )
    if resp.status_code == 200:
        return resp.json().get("status")
    return None


def upsert_member(server, api_key, audience_id, row, status_if_new, dry_run):
    email = row["email"].strip().lower()
    subscriber_hash = hashlib.md5(email.encode()).hexdigest()
    tag = CATEGORY_TAGS.get(row.get("category", ""), "Partner-Lead")

    payload = {
        "email_address": email,
        "status_if_new": status_if_new,
        "merge_fields": {
            "FIRMA": row.get("name", "")[:255],
            "ORT": row.get("city", "")[:255],
            "ADRESSE": row.get("street_address", "")[:255],
        },
        "tags": [tag],
    }

    if dry_run:
        print(f"  [DRY-RUN] würde anlegen (falls noch nicht vorhanden): {email} "
              f"({row.get('name')}, status_if_new={status_if_new}, tag={tag})")
        return "dry-run"

    status = existing_status(server, api_key, audience_id, subscriber_hash)
    if status in ACTIVE_STATUSES:
        print(f"  bereits aktiv in Mailchimp ({status}), übersprungen: {email}")
        return "skipped_existing"
    if status is not None:
        print(f"  Datensatz existiert mit Status '{status}' (z.B. archiviert/"
              f"abgemeldet) - versuche trotzdem anzulegen: {email}")

    resp = mailchimp_request(
        "PUT",
        f"/lists/{audience_id}/members/{subscriber_hash}",
        server, api_key, json=payload,
    )
    if resp.status_code in (200, 201):
        return "ok"
    else:
        print(f"  FEHLER bei {email}: {resp.status_code} {resp.text[:200]}")
        return "error"


def main(argv=None):
    """argv=None liest von der Kommandozeile (normaler CLI-Aufruf).
    Wird auch von scraper/run_pipeline.py mit einer expliziten Liste
    aufgerufen, wenn --push-mailchimp gesetzt ist."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Tatsächlich in Mailchimp schreiben (ohne diesen Flag: nur Vorschau/Dry-Run)")
    parser.add_argument("--status", default="pending", choices=["pending", "subscribed"],
                         help="Mitgliedsstatus für NEUE Kontakte (Default: pending = Double-Opt-in-Mail wird von Mailchimp verschickt)")
    parser.add_argument("--input", default=config.READY_CSV)
    args = parser.parse_args(argv)

    if args.status == "subscribed":
        print("*** ACHTUNG: --status subscribed übergeht Mailchimps Double-Opt-in.")
        print("*** Das ist nur zulässig, wenn für JEDEN Kontakt in der Liste bereits")
        print("*** eine nachweisbare Einwilligung vorliegt. Für die rohe Scraper-")
        print("*** Liste ist das NICHT der Fall. Abbruch in 5 Sekunden, Ctrl+C zum Stoppen.")
        time.sleep(5)

    api_key = os.getenv("MAILCHIMP_API_KEY")
    server = os.getenv("MAILCHIMP_SERVER_PREFIX")
    audience_id = os.getenv("MAILCHIMP_AUDIENCE_ID")
    if not args.live:
        print("Dry-Run-Modus (Standard) - es wird NICHTS an Mailchimp gesendet.")
        print("Mit --live tatsächlich schreiben (benötigt gültige .env-Werte).\n")
    elif not all([api_key, server, audience_id]):
        sys.exit("Fehler: MAILCHIMP_API_KEY / MAILCHIMP_SERVER_PREFIX / "
                  "MAILCHIMP_AUDIENCE_ID fehlen in .env (siehe .env.example).")

    if args.live:
        verify_credentials(server, api_key, audience_id)

    with open(args.input, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("email")]

    print(f"{len(rows)} Kontakte mit E-Mail in {args.input}")
    print("Jeder Kontakt wird einzeln bei Mailchimp abgefragt (schon vorhanden?) "
          "und nur bei Bedarf neu angelegt.\n")

    results = {"ok": 0, "error": 0, "dry-run": 0, "skipped_existing": 0}
    for row in rows:
        outcome = upsert_member(server, api_key, audience_id, row, args.status, dry_run=not args.live)
        results[outcome] = results.get(outcome, 0) + 1
        if args.live:
            time.sleep(0.3)  # Mailchimp-Rate-Limits schonen (2 Requests/Kontakt: GET+PUT)

    print(f"\nZusammenfassung: {results}")


if __name__ == "__main__":
    main()
