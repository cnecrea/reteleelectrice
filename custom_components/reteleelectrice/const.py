"""Constante pentru integrarea Rețele Electrice România."""

from typing import Final

# ──────────────────────────────────────────────
# Domeniu & configurare implicită
# ──────────────────────────────────────────────
DOMAIN = "reteleelectrice"
DEFAULT_UPDATE = 3600  # secunde (1 oră)
ATTRIBUTION = "Date furnizate de Rețele Electrice România"

# ──────────────────────────────────────────────
# URL-uri portal Salesforce
# ──────────────────────────────────────────────
BASE_URL = "https://contulmeu.reteleelectrice.ro"
LOGIN_PAGE = f"{BASE_URL}/PEDRO_SiteLogin"
AURA_URL = f"{BASE_URL}/s/sfsites/aura"

# Salesforce org & Aura config
SFDC_ORG_ID = "00D24000000cvG0"
AURA_FWUID = "TXFWNVprQUZzQnEtNXVXYTFLQ2ppdzJEa1N5enhOU3R5QWl2VzNveFZTbGcxMy4tMjE0NzQ4MzY0OC4xMzEwNzIwMA"
AURA_APP_UID = "1537_wmTAUxhOaM_47EClrN56Dw"

# ──────────────────────────────────────────────
# Headere HTTP (browser-like)
# ──────────────────────────────────────────────
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9,ro;q=0.8",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

# ──────────────────────────────────────────────
# Mapare pagini VF pentru A4J calls
# ──────────────────────────────────────────────
VF_PAGE_MAP: dict[str, str] = {
    "CurveDiCaricoGraph": "PED_ProxyCallWSAsync_Curve_VF",
    "RetriveSingleSelf": "PED_ProxyCallWSAsynSingleSelf_VF",
    "PowerOutages": "PED_ProxyCallWSAsynPowerOutages_VF",
    "FindOutMeterHistoryData": "PED_ProxyCallWSAsync_SmartMeter_Vf",
    "FindOutMeterCurrentData": "PED_ProxyCallWSAsynSmartMeterCurrentData",
    "FindOutMeterIstantData": "PED_ProxyCallWSAsynSmartMeterIstantData",
}

# ──────────────────────────────────────────────
# Mapare luni → română
# ──────────────────────────────────────────────
MONTHS_EN_RO: dict[str, str] = {
    "January": "ianuarie",
    "February": "februarie",
    "March": "martie",
    "April": "aprilie",
    "May": "mai",
    "June": "iunie",
    "July": "iulie",
    "August": "august",
    "September": "septembrie",
    "October": "octombrie",
    "November": "noiembrie",
    "December": "decembrie",
}

MONTHS_NUM_RO: dict[str, str] = {
    "01": "ianuarie",
    "02": "februarie",
    "03": "martie",
    "04": "aprilie",
    "05": "mai",
    "06": "iunie",
    "07": "iulie",
    "08": "august",
    "09": "septembrie",
    "10": "octombrie",
    "11": "noiembrie",
    "12": "decembrie",
}

# ──────────────────────────────────────────────
# Licențiere
# ──────────────────────────────────────────────
CONF_LICENSE_KEY = "license_key"
LICENSE_DATA_KEY = "reteleelectrice_license_manager"

LICENSE_PURCHASE_URL: Final = "https://hubinteligent.org/donate?ref=reteleelectrice"
