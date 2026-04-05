"""
Funcții utilitare pentru integrarea Rețele Electrice România.

Conține:
  - Formatare valută (RON) în format românesc
  - Formatare date în limba română
  - Conversie sigură la float
  - Construire adresă citibilă din datele POD
  - Mapping județe România (cod → nume complet)
  - Normalizare text
"""

from datetime import datetime

from .const import MONTHS_EN_RO, MONTHS_NUM_RO


# ── Mapping județe România ──────────────────────

JUDETE_RO: dict[str, str] = {
    "AB": "Alba",
    "AR": "Arad",
    "AG": "Argeș",
    "BC": "Bacău",
    "BH": "Bihor",
    "BN": "Bistrița-Năsăud",
    "BT": "Botoșani",
    "BV": "Brașov",
    "BR": "Brăila",
    "B":  "București",
    "BZ": "Buzău",
    "CS": "Caraș-Severin",
    "CL": "Călărași",
    "CJ": "Cluj",
    "CT": "Constanța",
    "CV": "Covasna",
    "DB": "Dâmbovița",
    "DJ": "Dolj",
    "GL": "Galați",
    "GR": "Giurgiu",
    "GJ": "Gorj",
    "HR": "Harghita",
    "HD": "Hunedoara",
    "IL": "Ialomița",
    "IS": "Iași",
    "IF": "Ilfov",
    "MM": "Maramureș",
    "MH": "Mehedinți",
    "MS": "Mureș",
    "NT": "Neamț",
    "OT": "Olt",
    "PH": "Prahova",
    "SM": "Satu Mare",
    "SJ": "Sălaj",
    "SB": "Sibiu",
    "SV": "Suceava",
    "TR": "Teleorman",
    "TM": "Timiș",
    "TL": "Tulcea",
    "VS": "Vaslui",
    "VL": "Vâlcea",
    "VN": "Vrancea",
}


# ── Formatare valută ────────────────────────────


def format_ron(value: float) -> str:
    """Formatează o valoare numerică în format românesc (1.234,56)."""
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


# ── Formatare date ──────────────────────────────


def format_date_ro(date_str: str, input_format: str = "%Y-%m-%d") -> str:
    """Formatează o dată ca '5 ianuarie 2025'."""
    try:
        parsed = datetime.strptime(date_str, input_format)
        month = MONTHS_EN_RO.get(parsed.strftime("%B"), "necunoscut")
        return f"{parsed.day} {month} {parsed.year}"
    except (ValueError, TypeError):
        return "Necunoscut"


def format_date_ro_ddmmyyyy(date_str: str) -> str:
    """Formatează o dată din format DD.MM.YYYY ca '5 ianuarie 2025'."""
    try:
        parsed = datetime.strptime(date_str.split(" ")[0], "%d.%m.%Y")
        month = MONTHS_EN_RO.get(parsed.strftime("%B"), "necunoscut")
        return f"{parsed.day} {month} {parsed.year}"
    except (ValueError, TypeError):
        return date_str or "Necunoscut"


# ── Conversie sigură la float ───────────────────


def safe_float(value, default: float = 0.0) -> float:
    """Conversie sigură la float (API-ul returnează string-uri)."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """Conversie sigură la int."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


# ── Mapping județ ───────────────────────────────


def get_judet(code: str) -> str:
    """Returnează numele complet al județului din codul scurt (ex: AB → Alba)."""
    return JUDETE_RO.get(code.upper().strip(), code) if code else "Necunoscut"


# ── Normalizare text ────────────────────────────


def normalize_title(value: str) -> str:
    """Normalizează text venit din API (de obicei ALL CAPS) în Title Case curat."""
    if not value:
        return ""

    value = value.strip().lower().title()

    replacements = {
        " Nr.": " nr.",
        " Ap.": " ap.",
        " Bl.": " bl.",
        " Sc.": " sc.",
        " Et.": " et.",
    }

    for wrong, correct in replacements.items():
        value = value.replace(wrong, correct)

    return value


# ── Construire adresă din POD ───────────────────


def build_pod_address(pod: dict) -> str:
    """Construiește adresa citibilă din datele unui POD.

    POD-ul are câmpul POD_Address__c dar și câmpuri individuale:
    City__c, County__c, Description_Street__c, House_Number__c, etc.
    """
    # Preferăm POD_Address__c dacă există
    addr = pod.get("POD_Address__c", "")
    if addr:
        return normalize_title(addr)

    parts: list[str] = []

    street = normalize_title(pod.get("Description_Street__c", ""))
    nr = pod.get("House_Number__c", "").strip()
    if street and nr:
        parts.append(f"{street} {nr}")
    elif street:
        parts.append(street)

    apt = pod.get("Apartment__c", "").strip()
    if apt:
        parts.append(f"ap. {apt}")

    city = normalize_title(pod.get("City__c", ""))
    if city:
        parts.append(city)

    county = pod.get("County__c", "")
    if county:
        parts.append(normalize_title(county))

    return ", ".join(parts) if parts else "Adresă necunoscută"


# ── HTML entity decode ──────────────────────────


def decode_html_entities(text: str) -> str:
    """Decodifică entitățile HTML (ex: &#259; → ă)."""
    if not text:
        return text
    import html
    return html.unescape(text)
