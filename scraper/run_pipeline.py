"""
Führt die Scraper-Schritte nacheinander aus:
  1. find_businesses.py   -> data/1_raw_leads.csv
  2. enrich_emails.py     -> data/2_enriched_leads.csv
  3. filter_chains.py     -> data/3_leads_ready.csv (+ excluded_chains.csv)
  4. (optional) mailchimp_import.py -> neue Kontakte nach Mailchimp

Standardmäßig macht Schritt 4 GAR NICHTS - erst mit --push-mailchimp
wird er überhaupt ausgeführt, und auch dann nur als Dry-Run, bis
zusätzlich --live angegeben wird. So bleibt "einmal aus Versehen alles
durchlaufen lassen" ungefährlich.

Nutzung:
  # Nur Leads sammeln/aufbereiten, nichts an Mailchimp senden
  python scraper/run_pipeline.py

  # Zusätzlich prüfen, was an Mailchimp gesendet würde (Dry-Run)
  python scraper/run_pipeline.py --push-mailchimp

  # Wirklich an Mailchimp senden (status_if_new=pending, Double-Opt-in)
  python scraper/run_pipeline.py --push-mailchimp --live

  # Schritt 1 überspringen (vorhandene raw_leads.csv weiterverwenden,
  # praktisch beim Testen)
  python scraper/run_pipeline.py --skip-fetch

Automatisch nur NEUE Leads:
  - find_businesses.py liefert bei jedem Lauf den aktuellen Gesamtbestand
    aus OpenStreetMap (kann neue, seit dem letzten Lauf hinzugekommene
    Betriebe enthalten).
  - mailchimp_import.py fragt vor jedem Import bei Mailchimp selbst nach,
    ob der Kontakt schon existiert (GET vor PUT) - nicht in einer
    lokalen Datei. Das ist bewusst so gebaut, damit die Pipeline auch in
    Umgebungen ohne dauerhaften Speicher funktioniert (z.B. als Render
    Cron Job, der bei jedem Lauf mit leerem Dateisystem startet). Wer
    die Pipeline regelmäßig laufen lässt, bekommt dadurch bei jedem
    Durchlauf nur die seither neu dazugekommenen Kontakte nach
    Mailchimp geschickt - keine doppelten Double-Opt-in-Mails an
    bereits angefragte Betriebe.
"""
import argparse
import sys

sys.path.insert(0, ".")

from scraper import find_businesses, enrich_emails, filter_chains  # noqa: E402
from mailchimp import mailchimp_import  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true",
                         help="Overpass-Abfrage überspringen, vorhandene raw_leads.csv nutzen")
    parser.add_argument("--push-mailchimp", action="store_true",
                         help="Nach dem Filtern zusätzlich mailchimp_import.py ausführen "
                              "(ohne --live weiterhin nur als Vorschau)")
    parser.add_argument("--live", action="store_true",
                         help="Nur zusammen mit --push-mailchimp: tatsächlich an Mailchimp senden")
    parser.add_argument("--status", default="pending", choices=["pending", "subscribed"],
                         help="Nur zusammen mit --push-mailchimp: Status für neue Kontakte (Default: pending)")
    args = parser.parse_args()

    if not args.skip_fetch:
        find_businesses.main()
    else:
        print("Überspringe Schritt 1 (--skip-fetch)")

    print()
    enrich_emails.main()
    print()
    filter_chains.main()

    print("\nPipeline (Leads) fertig. Alles außer bekannten Ketten liegt jetzt in")
    print("data/3_leads_ready.csv (kein manueller Zwischenschritt mehr).")

    if not args.push_mailchimp:
        print("\nHinweis: --push-mailchimp nicht gesetzt, es wurde NICHTS an "
              "Mailchimp gesendet. Manuell mit: python mailchimp/mailchimp_import.py --live")
        return

    print("\n--- Schritt 4: Mailchimp-Import ---")
    mc_argv = ["--status", args.status]
    if args.live:
        mc_argv.append("--live")
    else:
        print("(Dry-Run - mit zusätzlich --live würde wirklich geschrieben)")
    mailchimp_import.main(mc_argv)


if __name__ == "__main__":
    main()
