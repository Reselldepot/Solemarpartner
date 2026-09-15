"""
Zentrale Konfiguration für den SOLÉMAR Partner-Lead-Scraper.

Alle Werte hier anpassen statt in den einzelnen Skripten zu suchen.
"""

# --- Suchgebiet -------------------------------------------------------
# Freudenstadt, Schwarzwald (Marktplatz als Referenzpunkt)
ORIGIN_LAT = 48.4667
ORIGIN_LON = 8.4167
RADIUS_M = 30_000  # 30 km Umkreis

# --- Branchen (OpenStreetMap-Tags) ------------------------------------
# Overpass-Abfrage nutzt diese Tag-Kombinationen. Jede Kategorie bekommt
# ein sprechendes Label für die CSV-Ausgabe / Mailchimp-Tags.
OSM_CATEGORIES = {
    "friseur":  [("shop", "hairdresser")],
    "beauty":   [("shop", "beauty"), ("shop", "cosmetics")],
    "tattoo":   [("shop", "tattoo"), ("craft", "tattoo")],
}

# --- Filter: bekannte Ketten -------------------------------------------
# Namensfragmente (klein geschrieben), die auf eine Franchise-/Ketten-
# marke hindeuten. Liste ist NICHT vollständig -> needs_review.csv immer
# manuell gegenprüfen, bevor importiert/angeschrieben wird.
CHAIN_BLOCKLIST = [
    "klier",
    "boyens",
    "dessange",
    "toni & guy",
    "toni&guy",
    "haarscharf gmbh",
    "stadtfriseur",
    "cut & go",
    "hairkiller",
    "hairexpress",
    "hair express",
    "beauty24",
    "douglas",
    "depot friseur",
    "amici parrucchieri",
    "haargenau gmbh",
    "sunpoint",
    "solarium24",
    "mac cosmetics",
    "yves rocher",
    "bodystreet",
]

# Rechtsformen/Zusätze, die beim Normalisieren des Namens entfernt werden,
# damit Dubletten-/Filialerkennung sauber funktioniert.
LEGAL_SUFFIXES = [
    "gmbh & co. kg", "gmbh & co kg", "gmbh", "e.k.", "e.v.", "ug",
    "inh.", "inhaberin", "inhaber",
]

# --- Netzwerk / Höflichkeit --------------------------------------------
USER_AGENT = "SolemarPartnerLeadResearch/1.0 (+kontakt@solemarperfume.com)"
REQUEST_TIMEOUT_S = 12
DELAY_BETWEEN_REQUESTS_S = 1.5  # nicht aggressiv crawlen

# --- Pfade ---------------------------------------------------------------
DATA_DIR = "data"
RAW_LEADS_CSV = f"{DATA_DIR}/1_raw_leads.csv"
ENRICHED_CSV = f"{DATA_DIR}/2_enriched_leads.csv"
READY_CSV = f"{DATA_DIR}/3_leads_ready.csv"
NEEDS_REVIEW_CSV = f"{DATA_DIR}/3_needs_review.csv"
EXCLUDED_CHAINS_CSV = f"{DATA_DIR}/3_excluded_chains.csv"
SENT_LOG_CSV = f"{DATA_DIR}/sent_log.csv"
