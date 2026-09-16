"""
Diagnose-Tool: Fragt für jede E-Mail aus data/3_leads_ready.csv den
TATSÄCHLICHEN Status direkt bei Mailchimp ab und zeigt eine Übersicht.

Hintergrund: Neue Kontakte werden von mailchimp_import.py standardmäßig
mit Status "pending" angelegt. Mailchimps Audience-Ansicht zeigt in der
Standardeinstellung oft nur "subscribed"-Kontakte prominent an bzw.
zählt nur diese in der Übersichtszahl - pending-Kontakte sind trotzdem
da, nur unter einem anderen Filter sichtbar. Dieses Skript zeigt genau,
was in Mailchimp wirklich steht, ohne im Dashboard suchen zu müssen.

Nutzung:
  python mailchimp/check_status.py
  python mailchimp/check_status.py --input data/3_leads_ready.csv
"""
import argparse
import csv
import hashlib
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, ".")
import config  # noqa: E402

load_dotenv()


def mailchimp_get(server, api_key, path):
    url = f"https://{server}.api.mailchimp.com/3.0{path}"
    try:
        return requests.get(url, auth=("anystring", api_key), timeout=15)
    except requests.exceptions.RequestException as exc:
        sys.exit(f"Netzwerkfehler bei {url}: {exc}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=config.READY_CSV)
    args = parser.parse_args()

    api_key = os.getenv("MAILCHIMP_API_KEY")
    server = os.getenv("MAILCHIMP_SERVER_PREFIX")
    audience_id = os.getenv("MAILCHIMP_AUDIENCE_ID")
    if not all([api_key, server, audience_id]):
        sys.exit("Fehler: MAILCHIMP_API_KEY / MAILCHIMP_SERVER_PREFIX / "
                  "MAILCHIMP_AUDIENCE_ID fehlen in .env")

    with open(args.input, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("email")]

    print(f"Prüfe {len(rows)} E-Mails aus {args.input} direkt bei Mailchimp...\n")

    counts = {}
    for row in rows:
        email = row["email"].strip().lower()
        subscriber_hash = hashlib.md5(email.encode()).hexdigest()
        resp = mailchimp_get(
            server, api_key,
            f"/lists/{audience_id}/members/{subscriber_hash}?fields=status,email_address",
        )
        if resp.status_code == 200:
            status = resp.json().get("status", "?")
        elif resp.status_code == 404:
            status = "NICHT VORHANDEN"
        else:
            status = f"FEHLER ({resp.status_code})"

        counts[status] = counts.get(status, 0) + 1
        print(f"  {email:45s} {row.get('name','')[:30]:30s} -> {status}")

    print("\n--- Zusammenfassung ---")
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:20s} {n}")

    print(
        "\nHinweis: 'pending' bedeutet, der Kontakt EXISTIERT in Mailchimp, "
        "hat aber die Double-Opt-in-Bestätigungsmail noch nicht angeklickt. "
        "Im Dashboard: Audience -> All contacts -> Filter/Segment auf "
        "'Pending' bzw. 'Non-subscribed' stellen, um sie zu sehen - die "
        "Übersichtszahl oben zählt meist nur 'subscribed'."
    )


if __name__ == "__main__":
    main()
