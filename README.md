# SOLÉMAR Partner-Lead-Pipeline

Findet unabhängige Friseurläden, Beauty-Salons und Tattoo-Studios im
30-km-Umkreis von Freudenstadt, reichert sie mit Kontakt-E-Mails an,
sortiert bekannte Ketten aus und unterstützt beim Anschreiben sowie
(optional) beim Import in Mailchimp. Dazu: eine fertige, auf das Design
von solemarperfume.com abgestimmte HTML-Mailvorlage für das
Partnerprogramm-Angebot.

## Bitte zuerst lesen: rechtliche Stolperfallen

Bevor irgendetwas "automatisch" an echte Adressen verschickt oder in
Mailchimp importiert wird, zwei Punkte, die den ganzen Ansatz betreffen:

1. **Mailchimp-Nutzungsbedingungen.** Mailchimp verbietet ausdrücklich
   den Import von Listen, die durch Scraping oder ohne nachweisbare
   Einwilligung entstanden sind. Ein Massenimport der rohen Scraper-
   Liste mit Status "subscribed" riskiert die Sperrung des gesamten
   Mailchimp-Accounts (Kampagnen, bestehende Kunden-Liste, alles).
2. **§7 UWG (Deutschland).** Werbung per E-Mail ohne vorherige
   Einwilligung ist grundsätzlich unzulässig – auch im B2B-Bereich –
   und kann zu kostenpflichtigen Abmahnungen führen.

**Deshalb ist die Pipeline bewusst zweigeteilt:**

- `outreach/send_outreach.py` verschickt eine **persönliche
  Einzel-E-Mail** an die im Impressum veröffentlichte
  Geschäftsadresse (das ist die von den Betrieben selbst für
  Geschäftsanfragen bestimmte Adresse, keine private Adresse). Das ist
  die in Deutschland übliche Form der B2B-Erstansprache – ein
  rechtliches Restrisiko bleibt trotzdem bestehen, ist aber deutlich
  geringer als ein Mailchimp-Massenversand.
- `mailchimp/mailchimp_import.py` legt neue Kontakte standardmäßig mit
  Status **"pending"** an (Mailchimp verschickt automatisch eine
  Bestätigungs-Mail, Double-Opt-in). Nur wer aktiv bestätigt, landet
  wirklich in der Marketing-Liste. Die schöne HTML-Vorlage
  (`email_template/partner_einladung.html`) ist für **spätere,
  legitime Mailchimp-Kampagnen** an diese bestätigten Kontakte gedacht
  – nicht für den kalten Erstkontakt.

Kurz: Erstkontakt = persönliche Mail. Mailchimp = erst, wenn jemand
zugestimmt hat. So bleibt der Mailchimp-Account sicher und das
rechtliche Risiko überschaubar.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# .env mit echten Zugangsdaten füllen (Mailchimp API-Key, SMTP-Zugang)
```

Getestet mit Python 3.10+. Auf diesem Rechner ist aktuell kein Python
installiert – bitte vor dem ersten Lauf `python --version` prüfen bzw.
Python von python.org installieren.

## 1. Leads finden, anreichern, filtern

```bash
python scraper/run_pipeline.py
```

Das macht drei Dinge nacheinander (auch einzeln aufrufbar):

| Schritt | Skript | Ergebnis |
|---|---|---|
| Betriebe finden (OpenStreetMap, 30 km um Freudenstadt) | `scraper/find_businesses.py` | `data/1_raw_leads.csv` |
| Fehlende E-Mails aus Impressum/Kontakt-Seite ergänzen | `scraper/enrich_emails.py` | `data/2_enriched_leads.csv` |
| Bekannte Ketten raussortieren | `scraper/filter_chains.py` | `data/3_leads_ready.csv` + `3_needs_review.csv` + `3_excluded_chains.csv` |

**Warum OpenStreetMap statt Google Maps/Gelbe Seiten scrapen?** Freie,
offen lizenzierte Daten – kein Verstoß gegen fremde Nutzungsbedingungen.
Nachteil: OSM-Abdeckung ist in Kleinstädten lückenhaft, die Liste ist
eine gute Grundlage, aber nicht vollständig. Ein Testlauf hat für die
Region bereits **124 Treffer** geliefert (Friseure, Beauty, Tattoo),
davon ~20 mit Website und 8 mit direkt hinterlegter E-Mail – die
Website-Anreicherung (Schritt 2) holt bei den meisten übrigen noch die
Impressum-Adresse nach.

**Ketten-Filter ist unvollständig.** Die Blockliste in `config.py`
(`CHAIN_BLOCKLIST`) enthält bekannte Marken, ist aber keine
vollständige Datenbank. Zusätzlich werden Namen, die mehrfach im
Datensatz auftauchen (= möglicherweise mehrere Filialen), automatisch
nach `needs_review.csv` verschoben statt gelöscht.

➜ **Vor dem nächsten Schritt `data/3_needs_review.csv` kurz von Hand
durchsehen** und ggf. einzelne Zeilen manuell in `3_leads_ready.csv`
verschieben oder ergänzen.

## 2. Persönliche Erstansprache verschicken

```bash
# 1. Vorschau (Standard, verschickt nichts)
python outreach/send_outreach.py

# 2. Testlauf – alle Mails gehen an SMTP_TEST_OVERRIDE_TO aus der .env
python outreach/send_outreach.py --test

# 3. Echter Versand
python outreach/send_outreach.py --live
```

Text der Mail: `outreach/email_text_template.txt` (auf Deutsch, mit
Platzhaltern `{{name}}`, `{{ort}}` – bitte vor dem Live-Versand einmal
selbst lesen und ggf. den Ton anpassen). Ein `data/sent_log.csv`
verhindert, dass beim erneuten Ausführen doppelt angeschrieben wird.

## 3. Mailchimp-Vorlage für die spätere Kampagne

`email_template/partner_einladung.html` ist eine fertige,
tabellenbasierte E-Mail-Vorlage im SOLÉMAR-Design – kompatibel mit
Outlook, Gmail, Apple Mail etc.

**Design direkt von solemarperfume.com übernommen:**

| Element | Wert |
|---|---|
| Hintergrund | `#FAF6EF` (Creme) |
| Text/Buttons | `#2A1A0E` (dunkles Braun) |
| Akzent | `#DCBF8E` (warmes Gold) |
| Schrift Headlines | Cormorant (Serif) |
| Schrift Fließtext | Jost (Sans, Google Fonts) |
| Bilder | Original-Bilder vom Shopify-Shop (Logo, Hero-Foto, Flakon-Foto) |
| Tonalität | "Ein Duft, der nicht laut ist – aber unvergesslich." |

**So importierst du sie in Mailchimp:**

1. Mailchimp → *Campaigns* → *Create* → *Email* → Vorlage wählen →
   **"Code your own"** → **"Paste in code"**.
2. Kompletten Inhalt von `email_template/partner_einladung.html`
   einfügen → Save.
3. Unter *Audience* → *Settings* → *Merge fields* zwei Felder anlegen,
   falls noch nicht vorhanden:
   - `FIRMA` (Text) – Firmenname
   - `ORT` (Text) – Stadt
   (Diese Feldnamen nutzt auch `mailchimp_import.py` beim Import, so
   passt beides zusammen.)
4. Absenderadresse & Postanschrift in den Mailchimp-Audience-Settings
   hinterlegen (füllt automatisch `*|LIST:ADDRESS|*` im Footer).
5. Der Button-Link führt aktuell direkt auf Instagram
   (`https://ig.me/m/solemarperfume` – Metas offizieller "Nachricht
   senden"-Link, öffnet auf dem Handy sofort den DM-Chat mit
   @solemarperfume). Sobald es eine eigene Partnerprogramm-Seite gibt,
   den Link in `email_template/partner_einladung.html` entsprechend
   austauschen.

## 4. Import in Mailchimp (nur für bestätigte Kontakte!)

```bash
# Vorschau, schreibt nichts
python mailchimp/mailchimp_import.py

# Echter Import, Status "pending" (Double-Opt-in-Mail von Mailchimp)
python mailchimp/mailchimp_import.py --live
```

Siehe ausführlichen Warnhinweis im Skript-Kopf. `--status subscribed`
ist absichtlich nur mit zusätzlicher Bestätigung nutzbar und sollte nur
für Kontakte verwendet werden, die nachweislich zugestimmt haben.

**Läuft das automatisch mit durch, wenn ich die Pipeline starte?**
Nicht ohne dass du es explizit anforderst. `run_pipeline.py` macht den
Mailchimp-Schritt standardmäßig gar nicht. Erst mit `--push-mailchimp`
wird er überhaupt ausgeführt (dann zunächst wieder nur als Vorschau),
und erst zusätzlich mit `--live` wird wirklich geschrieben:

```bash
python scraper/run_pipeline.py --push-mailchimp --live
```

Dabei bleibt der Status weiterhin standardmäßig `pending`
(Double-Opt-in) - das Skript umgeht also weiterhin nicht die
Einwilligung, nur weil es jetzt in einem Befehl läuft.

**"Nur neue Leads" bei wiederholten Läufen:** `mailchimp_import.py`
fragt vor jedem Import direkt bei Mailchimp nach, ob die E-Mail dort
schon existiert, und überspringt sie in dem Fall. Wenn du die Pipeline
also regelmäßig laufen lässt, werden nur Betriebe, die noch nicht in
der Audience sind, überhaupt neu angelegt - bereits bearbeitete
Kontakte bekommen keine zweite Double-Opt-in-Mail. Das funktioniert
absichtlich ohne lokale Merkliste, damit es auch auf einem Host ohne
dauerhaften Speicher zuverlässig läuft (siehe Abschnitt 5, Render Cron
Job).

## 5. Automatisch laufen lassen (Render Cron Job)

Damit die Pipeline nicht von Hand gestartet werden muss, läuft sie am
einfachsten als **Render Cron Job**: ein Dienst, der nur zum geplanten
Zeitpunkt kurz startet, das Skript einmal durchlaufen lässt und sich
danach wieder beendet. Bewusst **kein** Background Worker (der würde
dauerhaft laufen und dauerhaft kosten, obwohl das Skript nur ein paar
Minuten pro Woche braucht) – siehe Begründung auch in `render.yaml`.

**Wichtig für das Verständnis:** Cron Jobs bei Render haben **kein
dauerhaftes Dateisystem** zwischen zwei Läufen (Render unterstützt dort
keine Disks). Jeder Lauf startet komplett neu. Deshalb prüft
`mailchimp_import.py` vor jedem Import direkt bei Mailchimp selbst
("gibt es diese E-Mail schon in der Audience?"), statt sich auf eine
lokale Log-Datei zu verlassen – so bleibt "nur neue Leads verarbeiten"
auch ohne dauerhaften Speicher zuverlässig.

### Schritt 1: Auf GitHub pushen

Lokal ist hier bereits ein Git-Repo mit einem ersten Commit
vorbereitet (`.env` ist über `.gitignore` ausgeschlossen, es landen
also keine Zugangsdaten auf GitHub). Fehlt noch: das leere Repo auf
GitHub anlegen und verknüpfen.

1. Auf [github.com/new](https://github.com/new) ein neues, **leeres**
   Repository anlegen (kein README/.gitignore auswählen – das gibt's
   hier schon). Sichtbarkeit: **Private** empfohlen, da im Code die
   Provisions-/Rabattlogik und interne Geschäftsdetails stehen.
2. Danach lokal:
   ```bash
   git remote add origin https://github.com/<dein-name>/<repo-name>.git
   git push -u origin main
   ```

### Schritt 2: Render Blueprint verbinden

1. [dashboard.render.com](https://dashboard.render.com) → **New** →
   **Blueprint** → das eben gepushte GitHub-Repo auswählen (beim
   ersten Mal muss GitHub einmalig mit Render verknüpft werden).
2. Render erkennt `render.yaml` automatisch und zeigt den Dienst
   `solemar-partner-leads` (Typ: Cron Job) zur Bestätigung an.
3. Render fragt dabei nach den drei Umgebungsvariablen
   `MAILCHIMP_API_KEY`, `MAILCHIMP_SERVER_PREFIX`,
   `MAILCHIMP_AUDIENCE_ID` – hier die echten Werte eintragen. Diese
   Werte werden nur bei Render gespeichert, nicht im Repo.
4. **Apply/Create** klicken – fertig. Der Cron Job läuft ab jetzt
   automatisch jeden Montag 06:00 UTC (Zeitplan in `render.yaml` unter
   `schedule` änderbar, Cron-Syntax, danach neu pushen).

Kosten: Render-Cron-Jobs sind kein Gratis-Feature, es fällt eine kleine
monatliche Mindestgebühr an (aktuelle Preise auf
[render.com/pricing](https://render.com/pricing) prüfen).

**Vorher nicht vergessen:** die Merge-Felder `FIRMA` und `ORT` müssen
in der Mailchimp-Audience existieren (siehe Abschnitt 3), sonst gehen
Firmenname/Stadt beim automatischen Import verloren.

## Was hier NICHT enthalten ist (bewusst außerhalb des Scopes)

Das beschriebene Partnerprogramm – eigenes Login, Live-Übersicht der
Verkäufe/Provisionen pro Code, PayPal-/Bank-Auszahlung, QR-Code- und
Rabattcode-Generierung – ist im Kern ein **eigenständiges
Affiliate-/Referral-System**, kein E-Mail-Thema mehr. Das lässt sich
grundsätzlich selbst bauen, ist aber ein separates, größeres Projekt
(Datenbank, Auth, Zahlungsanbindung, Betrugsschutz bei Provisionen
etc.). Schneller und günstiger ist in der Praxis meist eine fertige
Shopify-App dafür, z. B. **Shopify Collabs**, **Refersion** oder
**LoyaltyLion/ReferralCandy** – die bringen QR-/Rabattcodes,
Provisions-Tracking und PayPal-Auszahlung bereits mit und lassen sich
in wenigen Stunden statt Wochen einrichten. Gerne baue ich das als
nächsten Schritt mit auf, wenn gewünscht.

## Projektstruktur

```
config.py                          Zentrale Einstellungen (Ort, Radius, Blockliste)
scraper/
  find_businesses.py               Schritt 1: OpenStreetMap-Suche
  enrich_emails.py                 Schritt 2: E-Mail aus Impressum/Kontakt
  filter_chains.py                 Schritt 3: Ketten raussortieren
  run_pipeline.py                  Alle drei Schritte nacheinander
outreach/
  email_text_template.txt          Text der persönlichen Erstansprache
  send_outreach.py                 SMTP-Einzelversand mit Sent-Log
mailchimp/
  mailchimp_import.py              Import in Mailchimp-Audience (Double-Opt-in)
email_template/
  partner_einladung.html           Mailchimp-Kampagnen-Vorlage im SOLÉMAR-Design
data/                               Wird von den Skripten befüllt (CSV-Ausgaben)
.env.example                        Vorlage für Zugangsdaten
render.yaml                         Render-Blueprint (Cron Job, siehe Abschnitt 5)
.python-version                     Pinnt die Python-Version für Render
```
