"""
Versendet die persönliche Erstansprache (outreach/email_text_template.txt)
einzeln per SMTP an jeden Betrieb aus data/3_leads_ready.csv.

Warum SMTP statt Mailchimp-Kampagne für den Erstkontakt?
Mailchimp-Kampagnen sind für Newsletter an Leute gedacht, die bereits
zugestimmt haben ("Audience"). Ein Massenversand an gescrapte
Geschäftsadressen ohne Einwilligung verstößt gegen Mailchimps eigene
Regeln (Sperr-Risiko für den ganzen Account) und ist in Deutschland als
E-Mail-Werbung ohne Einwilligung nach §7 UWG riskant.

Eine einzelne, persönlich adressierte Geschäfts-E-Mail an die im
Impressum veröffentlichte Kontaktadresse mit einem konkreten,
individuellen Kooperationsangebot ist die deutlich üblichere und
rechtlich vertretbarere Form der Erstansprache (klassische B2B-Akquise-
E-Mail) – ein Restrisiko bleibt trotzdem bestehen, siehe README.md.

Sicherheitsfeatures:
- Standardmäßig Dry-Run (zeigt nur, was verschickt würde)
- --test schickt ALLE Mails an SMTP_TEST_OVERRIDE_TO zur Kontrolle
- Führt data/sent_log.csv, damit bei erneutem Lauf niemand doppelt
  angeschrieben wird
- Pause zwischen den Mails, um nicht wie ein Spam-Bot auszusehen
"""
import argparse
import csv
import os
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, ".")
import config  # noqa: E402

load_dotenv()

TEMPLATE_PATH = Path(__file__).parent / "email_text_template.txt"


def load_already_sent():
    if not os.path.exists(config.SENT_LOG_CSV):
        return set()
    with open(config.SENT_LOG_CSV, encoding="utf-8-sig") as f:
        return {row["email"].lower() for row in csv.DictReader(f)}


def append_sent_log(email):
    file_exists = os.path.exists(config.SENT_LOG_CSV)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.SENT_LOG_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "timestamp"])
        writer.writerow([email, time.strftime("%Y-%m-%d %H:%M:%S")])


def render(template: str, row: dict, absender_name: str, absender_email: str) -> str:
    return (
        template
        .replace("{{name}}", row.get("name", "Ihr Team"))
        .replace("{{ort}}", row.get("city", "der Region"))
        .replace("{{absender_name}}", absender_name)
        .replace("{{absender_email}}", absender_email)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Tatsächlich verschicken (sonst nur Vorschau)")
    parser.add_argument("--test", action="store_true", help="Live, aber alle Mails an SMTP_TEST_OVERRIDE_TO umleiten")
    parser.add_argument("--input", default=config.READY_CSV)
    parser.add_argument("--limit", type=int, default=None, help="Nur die ersten N (unversandten) Kontakte bearbeiten")
    args = parser.parse_args()

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_name = os.getenv("SMTP_FROM_NAME", "SOLÉMAR")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "")
    test_override_to = os.getenv("SMTP_TEST_OVERRIDE_TO")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    already_sent = load_already_sent()

    with open(args.input, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("email")]

    todo = [r for r in rows if r["email"].strip().lower() not in already_sent]
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(rows)} Kontakte insgesamt, {len(already_sent)} bereits angeschrieben, "
          f"{len(todo)} jetzt fällig.\n")

    if args.test and not test_override_to:
        sys.exit("Fehler: --test benötigt SMTP_TEST_OVERRIDE_TO in .env")

    server = None
    if args.live or args.test:
        if not all([smtp_host, smtp_user, smtp_password, from_email]):
            sys.exit("Fehler: SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM_EMAIL fehlen in .env")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_user, smtp_password)

    for row in todo:
        body = render(template, row, from_name, from_email)
        subject_line, _, body_text = body.partition("\n\n")
        subject = subject_line.replace("Betreff:", "").strip()

        to_addr = test_override_to if args.test else row["email"].strip()

        if not args.live and not args.test:
            print(f"[DRY-RUN] An: {to_addr}  Betreff: {subject}")
            continue

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_addr
        msg.set_content(body_text)

        server.send_message(msg)
        print(f"Gesendet an {to_addr} ({row.get('name')})")

        if not args.test:
            append_sent_log(row["email"].strip().lower())

        time.sleep(2)  # nicht wie ein Bot wirken, SMTP-Provider-Limits schonen

    if server:
        server.quit()

    print("\nFertig.")


if __name__ == "__main__":
    main()
