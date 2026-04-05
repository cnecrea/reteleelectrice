"""
API Manager pentru integrarea Rețele Electrice România.

Convertire async a reteleelectrice_login.py.
Portal: contulmeu.reteleelectrice.ro (Salesforce Experience Cloud)

Auth Flow:
    1. GET  PEDRO_SiteLogin → extrage ViewState
    2. POST PEDRO_SiteLogin → credențiale + ViewState
    3. Parse JS redirect → frontdoor.jsp?sid=...
    4. GET  frontdoor.jsp → stabilește session cookies
    5. GET  /s/ → extrage aura fwuid + aura token

API-uri:
    - Aura Actions (getUserName, getAccountInfo, getPODs, etc.)
    - VF A4J proxy (PowerOutages, ReadingArchive, SmartMeter)
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AURA_APP_UID,
    AURA_FWUID,
    AURA_URL,
    BASE_URL,
    BROWSER_HEADERS,
    LOGIN_PAGE,
    VF_PAGE_MAP,
)

_LOGGER = logging.getLogger(__name__)

# Timeout global pentru request-uri (secunde)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
VF_TIMEOUT = aiohttp.ClientTimeout(total=60)  # VF calls pot fi lente (WS extern)


class ReteleElectriceAPI:
    """Manager API async pentru integrarea Rețele Electrice România."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
    ) -> None:
        self._hass = hass
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._aura_token: str | None = None
        self._action_counter = 0
        self._logged_in = False
        # Cookie jar separat (trebuie să rețină sesiunea Salesforce)
        self._cookie_jar = aiohttp.CookieJar(unsafe=True)

    def _get_session(self) -> aiohttp.ClientSession:
        """Returnează o sesiune HTTP cu cookie jar propriu."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=self._cookie_jar,
                headers=BROWSER_HEADERS,
            )
        return self._session

    async def async_close(self) -> None:
        """Închide sesiunea HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ===================================================================
    # LOGIN (Salesforce Visualforce)
    # ===================================================================

    async def async_login(self) -> bool:
        """Autentificare completă. Returnează True la succes."""
        session = self._get_session()
        self._logged_in = False

        try:
            # --- Pas 1: GET login page ---
            login_url = (
                f"{LOGIN_PAGE}"
                f"?startURL=%2Fs%2F"
                f"&refURL=https%3A%2F%2Fcontulmeu.reteleelectrice.ro%2Fs%2F"
            )
            _LOGGER.debug("[ReteleElectrice] Pas 1: GET login page...")
            async with session.get(
                login_url,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error(
                        "[ReteleElectrice] Login page HTTP %d", resp.status
                    )
                    return False
                html = await resp.text()
                login_page_url = str(resp.url)

            # --- Pas 2: Parsează formularul VF ---
            _LOGGER.debug("[ReteleElectrice] Pas 2: Parsez formularul VF...")
            soup = BeautifulSoup(html, "html.parser")

            viewstate = self._extract_field(soup, "com.salesforce.visualforce.ViewState")
            viewstate_ver = self._extract_field(soup, "com.salesforce.visualforce.ViewStateVersion")
            viewstate_mac = self._extract_field(soup, "com.salesforce.visualforce.ViewStateMAC")

            if not viewstate:
                _LOGGER.error("[ReteleElectrice] ViewState nu a fost găsit în login page")
                return False

            form = soup.find("form", {"id": "loginPage:loginForm"}) or soup.find("form")
            form_id = form.get("id", "loginPage:loginForm") if form else "loginPage:loginForm"
            username_field = self._find_input_name(soup, ["username", "email"])
            password_field = self._find_input_name(soup, ["password", "pw"])
            submit_field = self._find_submit_name(soup)

            # --- Pas 3: POST credențiale ---
            _LOGGER.debug("[ReteleElectrice] Pas 3: POST credențiale...")
            payload = {
                form_id: form_id,
                username_field: self._username,
                password_field: self._password,
                submit_field: submit_field,
                "com.salesforce.visualforce.ViewState": viewstate,
                "com.salesforce.visualforce.ViewStateVersion": viewstate_ver,
                "com.salesforce.visualforce.ViewStateMAC": viewstate_mac,
            }

            form_action = (
                f"{LOGIN_PAGE}"
                f"?startURL=%2Fs%2F"
                f"&refURL=https%3A%2F%2Fcontulmeu.reteleelectrice.ro%2Fs%2F"
            )

            async with session.post(
                form_action,
                data=payload,
                headers={
                    **BROWSER_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": BASE_URL,
                    "Referer": login_page_url,
                    "Cache-Control": "max-age=0",
                },
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                post_html = await resp.text()

            # --- Pas 4: Detectează JS redirect către frontdoor.jsp ---
            _LOGGER.debug("[ReteleElectrice] Pas 4: Detectez JS redirect...")
            frontdoor_url = None
            js_match = re.search(
                r"window\.location\.(?:replace|href)\s*[=\(]\s*['\"]"
                r"(https?://[^'\"]*frontdoor\.jsp[^'\"]*)['\"]",
                post_html,
            )
            if not js_match:
                js_match = re.search(
                    r"handleRedirect\(['\"]"
                    r"(https?://[^'\"]*frontdoor\.jsp[^'\"]*)['\"]",
                    post_html,
                )

            if js_match:
                frontdoor_url = js_match.group(1)
                _LOGGER.debug("[ReteleElectrice] Frontdoor URL detectat")
            else:
                _LOGGER.error("[ReteleElectrice] Nu am detectat JS redirect")
                return False

            # --- Pas 5: GET frontdoor.jsp ---
            _LOGGER.debug("[ReteleElectrice] Pas 5: GET frontdoor.jsp...")
            async with session.get(
                frontdoor_url,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                _LOGGER.debug(
                    "[ReteleElectrice] Frontdoor status: %d", resp.status
                )

            # --- Pas 6: GET /s/ → extrage Aura token ---
            _LOGGER.debug("[ReteleElectrice] Pas 6: GET /s/ → aura token...")
            async with session.get(
                f"{BASE_URL}/s/",
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                s_html = await resp.text()

            # Aura token din cookie __Host-ERIC_PROD*
            self._aura_token = self._extract_aura_token_from_cookies()
            if not self._aura_token:
                self._aura_token = self._extract_aura_token_from_html(s_html)

            if self._aura_token:
                _LOGGER.debug("[ReteleElectrice] Aura token obținut: %s...", self._aura_token[:30])
            else:
                _LOGGER.warning("[ReteleElectrice] Aura token nu a fost găsit!")

            self._logged_in = True
            _LOGGER.info("[ReteleElectrice] Login reușit")
            return True

        except aiohttp.ClientError as err:
            _LOGGER.error("[ReteleElectrice] Eroare de rețea la login: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("[ReteleElectrice] Eroare neașteptată la login: %s", err)
            return False

    # ===================================================================
    # AURA API - Metode de nivel înalt
    # ===================================================================

    async def async_get_user_name(self) -> Optional[dict]:
        """Obține numele utilizatorului logat."""
        return await self._aura_call(
            descriptor="apex://PED_Utility/ACTION$getUserName",
            calling_descriptor="markup://c:PED_CustomProfileHeader",
        )

    async def async_get_account_info(self) -> Optional[dict]:
        """Obține informațiile contului (nume, adresă, CNP, etc.)."""
        return await self._aura_call(
            descriptor="apex://PED_Utility/ACTION$getAccountInfo",
            calling_descriptor="markup://c:PED_CustomProfileHeader",
        )

    async def async_get_contact_info(self) -> Optional[dict]:
        """Obține informațiile de contact."""
        return await self._aura_call(
            descriptor="apex://PED_Utility/ACTION$getContactInfo",
            calling_descriptor="markup://c:PED_CustomProfileHeader",
        )

    async def async_get_pods(self) -> Optional[list]:
        """Obține lista tuturor POD-urilor (puncte de consum)."""
        return await self._aura_call(
            descriptor="apex://PED_Utility/ACTION$getPODs",
            calling_descriptor="markup://c:PED_HomePage",
        )

    async def async_get_pod_details(self, pod_name: str) -> Optional[dict]:
        """Obține detaliile unui POD specific."""
        return await self._aura_call(
            descriptor="apex://PED_POD_Details_Controller/ACTION$getUserDetailsPodInformation",
            calling_descriptor="markup://c:PED_POD_Details",
            params={"PodName": pod_name},
        )

    async def async_get_pod_reading_details(self, pod_id: str) -> Optional[dict]:
        """Obține detaliile POD-ului pentru citiri (tip, CUI, CNP)."""
        return await self._aura_call(
            descriptor="apex://PED_ServizidiMisuraController/ACTION$PODDetails",
            calling_descriptor="markup://c:PED_Reading_Archive_Tab",
            params={"PodId": pod_id},
        )

    async def async_get_reading_archive_pod_details(self, pod_id: str) -> Optional[dict]:
        """Obține detaliile POD-ului via ReadingArchiveController."""
        return await self._aura_call(
            descriptor="apex://PED_ReadingArchiveController/ACTION$PODDetails",
            calling_descriptor="markup://c:PED_Reading_Archive_Tab",
            params={"PodId": pod_id},
        )

    async def async_check_is_client(self) -> Optional[bool]:
        """Verifică dacă utilizatorul curent este client."""
        return await self._aura_call(
            descriptor="apex://PED_Valori_di_Energia_Ctrl/ACTION$checkIsClient",
            calling_descriptor="markup://c:PED_Reading_Archive_Tab",
        )

    # ===================================================================
    # VF A4J Proxy — Reading Archive, Power Outages, Smart Meter
    # ===================================================================

    async def async_get_reading_archive(
        self,
        pod_name: str,
        start_date: str = "",
        end_date: str = "",
        cui: str = "",
        cnp: str = "",
    ) -> Optional[dict]:
        """Obține istoricul citirilor pentru un POD (RetriveSingleSelf)."""
        # Date default: ultimele 12 luni
        if not start_date or not end_date:
            now = datetime.now()
            one_year_ago = now - timedelta(days=365)
            if not start_date:
                start_date = one_year_ago.strftime("%d/%m/%Y 00:00:00")
            if not end_date:
                end_date = now.strftime("%d/%m/%Y 23:59:59")

        # Obținem CNP/CUI dacă lipsesc
        if not cnp and not cui:
            pod_details = await self.async_get_pod_reading_details(pod_name)
            if pod_details and isinstance(pod_details, dict):
                cnp = pod_details.get("cnp", "")
                cui = pod_details.get("cui", "")

            if not cnp and not cui:
                account = await self.async_get_account_info()
                if account and isinstance(account, dict):
                    cnp = account.get("CNP__c", "") or account.get("Fiscal_Code__c", "")
                    cui = account.get("Univocal_Code__c", "")

        # Construiește parametrii
        if cnp:
            method_params = ["", "", cnp, pod_name, start_date, end_date]
        elif cui:
            method_params = ["", cui, "", pod_name, start_date, end_date]
        else:
            method_params = ["", "", "", pod_name, start_date, end_date]

        return await self._call_vf_ws_async(
            method_name="RetriveSingleSelf",
            method_params=method_params,
        )

    async def async_get_power_outages(
        self, pod_name: str, language: str = "RO"
    ) -> Optional[dict]:
        """Obține informații despre întreruperile de curent pentru un POD."""
        method_params = [pod_name, language]
        return await self._call_vf_ws_async(
            method_name="PowerOutages",
            method_params=method_params,
        )

    async def async_get_smart_meter_data(
        self,
        pod_name: str,
        start_date: str = "",
        end_date: str = "",
        cnp: str = "",
    ) -> Optional[dict]:
        """Obține date istorice de la smart meter (FindOutMeterHistoryData).

        Pagina VF: PED_ProxyCallWSAsync_SmartMeter_Vf
        Parametri: [CNP, "", POD, startDate, endDate]
        Ambele date: "DD/MM/YYYY 00:00:00"
        """
        # Obținem CNP dacă nu e furnizat
        if not cnp:
            account = await self.async_get_account_info()
            if account and isinstance(account, dict):
                cnp = account.get("CNP__c", "") or account.get("Fiscal_Code__c", "")
            if not cnp:
                pod_details = await self.async_get_pod_reading_details(pod_name)
                if pod_details and isinstance(pod_details, dict):
                    cnp = pod_details.get("cnp", "")

        if not cnp:
            _LOGGER.warning("[ReteleElectrice] Smart meter: CNP nu a fost găsit!")

        # Default: ultimele 90 de zile
        if not start_date or not end_date:
            now = datetime.now()
            start = now - timedelta(days=90)
            if not start_date:
                start_date = start.strftime("%d/%m/%Y") + " 00:00:00"
            if not end_date:
                end_date = now.strftime("%d/%m/%Y") + " 00:00:00"

        method_params = [cnp, "", pod_name, start_date, end_date]
        return await self._call_vf_ws_async(
            method_name="FindOutMeterHistoryData",
            method_params=method_params,
        )

    async def async_get_smart_meter_current(
        self,
        pod_name: str,
        cnp: str = "",
    ) -> Optional[dict]:
        """Obține date curente de la smart meter (FindOutMeterCurrentData)."""
        if not cnp:
            account = await self.async_get_account_info()
            if account and isinstance(account, dict):
                cnp = account.get("CNP__c", "") or account.get("Fiscal_Code__c", "")

        method_params = [cnp, "", pod_name]
        return await self._call_vf_ws_async(
            method_name="FindOutMeterCurrentData",
            method_params=method_params,
        )

    async def async_get_smart_meter_instant(
        self,
        pod_name: str,
        cnp: str = "",
    ) -> Optional[dict]:
        """Obține date instantanee de la smart meter (FindOutMeterIstantData)."""
        if not cnp:
            account = await self.async_get_account_info()
            if account and isinstance(account, dict):
                cnp = account.get("CNP__c", "") or account.get("Fiscal_Code__c", "")

        method_params = [cnp, "", pod_name]
        return await self._call_vf_ws_async(
            method_name="FindOutMeterIstantData",
            method_params=method_params,
        )

    # ===================================================================
    # Visualforce Web Service Proxy (A4J AJAX Form Submit) — async
    # ===================================================================

    async def _call_vf_ws_async(
        self, method_name: str, method_params: list
    ) -> Optional[dict]:
        """Apelează un web service extern prin Visualforce A4J form submit."""
        vf_page_name = VF_PAGE_MAP.get(method_name)
        if not vf_page_name:
            return {"status": "error", "method": method_name, "error": "Unknown VF page"}

        vf_url = f"{BASE_URL}/{vf_page_name}"
        session = self._get_session()

        # --- Pas 1: GET pagina VF pentru ViewState ---
        _LOGGER.debug("[ReteleElectrice] A4J: GET %s", vf_url)
        try:
            async with session.get(
                vf_url, timeout=REQUEST_TIMEOUT, allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    return {"status": "vf_page_error", "method": method_name, "code": resp.status}
                html = await resp.text()
        except Exception as e:
            return {"status": "vf_get_failed", "method": method_name, "error": str(e)}

        soup = BeautifulSoup(html, "html.parser")

        # --- Pas 2: Extrage ViewState ---
        viewstate = self._extract_field(soup, "com.salesforce.visualforce.ViewState")
        viewstate_ver = self._extract_field(soup, "com.salesforce.visualforce.ViewStateVersion")
        viewstate_mac = self._extract_field(soup, "com.salesforce.visualforce.ViewStateMAC")

        if not viewstate:
            _LOGGER.error("[ReteleElectrice] A4J: ViewState nu a fost găsit!")
            return {"status": "vf_no_viewstate", "method": method_name}

        # --- Pas 3: Identifică form ID și A4J action ID ---
        form = soup.find("form")
        form_id = form.get("id", "j_id0:j_id2") if form else "j_id0:j_id2"
        form_action = form.get("action", f"/{vf_page_name}") if form else f"/{vf_page_name}"

        a4j_action_id = None
        invoke_match = re.search(
            r"invoke\s*=\s*function\s*\(\s*\)\s*\{.*?"
            r"A4J\.AJAX\.Submit\s*\(\s*'([^']+)'\s*,\s*null\s*,\s*\{"
            r".*?'similarityGroupingId'\s*:\s*'([^']+)'"
            r".*?'([^']+)'\s*:\s*'([^']+)'",
            html,
            re.DOTALL,
        )
        if invoke_match:
            a4j_action_id = invoke_match.group(2)
        else:
            a4j_match = re.search(r"'(j_id\d+:j_id\d+:j_id\d+)'", html)
            if a4j_match:
                a4j_action_id = a4j_match.group(1)
            else:
                a4j_action_id = f"{form_id}:j_id3"

        # --- Pas 4: Construiește POST data ---
        params_string = ",".join(str(p) for p in method_params)

        post_data = {
            "AJAXREQUEST": "_viewRoot",
            form_id: form_id,
            "methodN": method_name,
            "params": params_string,
            "uniqueId": f"script_{int(time.time())}",
            "com.salesforce.visualforce.ViewState": viewstate,
            "com.salesforce.visualforce.ViewStateVersion": viewstate_ver,
            "com.salesforce.visualforce.ViewStateMAC": viewstate_mac,
            a4j_action_id: a4j_action_id,
        }

        viewstate_csrf = self._extract_field(soup, "com.salesforce.visualforce.ViewStateCSRF")
        if viewstate_csrf:
            post_data["com.salesforce.visualforce.ViewStateCSRF"] = viewstate_csrf

        _LOGGER.debug(
            "[ReteleElectrice] A4J: POST %s | method=%s, params=%s",
            form_action, method_name, params_string,
        )

        # --- Pas 5: POST ---
        post_url = f"{BASE_URL}{form_action}" if form_action.startswith("/") else form_action
        try:
            async with session.post(
                post_url,
                data=post_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "*/*",
                    "Referer": vf_url,
                    "Origin": BASE_URL,
                },
                timeout=VF_TIMEOUT,
            ) as resp2:
                if resp2.status != 200:
                    return {
                        "status": "vf_post_error",
                        "method": method_name,
                        "http_status": resp2.status,
                    }
                response_text = await resp2.text()
        except Exception as e:
            return {"status": "vf_post_failed", "method": method_name, "error": str(e)}

        _LOGGER.debug(
            "[ReteleElectrice] A4J: Response len=%d", len(response_text)
        )

        # --- Pas 6: Parsează A4J response ---
        result = self._parse_a4j_response(response_text, method_name)
        if result is not None:
            _LOGGER.debug("[ReteleElectrice] A4J: SUCCESS — date obținute pentru %s", method_name)
            return result

        return {
            "status": "a4j_no_data_in_response",
            "method": method_name,
            "response_length": len(response_text),
        }

    # ===================================================================
    # AURA API - Nivel scăzut (async)
    # ===================================================================

    async def _aura_call(
        self,
        descriptor: str,
        params: dict = None,
        calling_descriptor: str = "UNKNOWN",
        version: str = None,
        storable: bool = False,
    ) -> Optional[Any]:
        """Execută un Aura action call (async)."""
        if not self._aura_token:
            _LOGGER.error("[ReteleElectrice] Aura token lipsă. Fă login mai întâi.")
            return None

        session = self._get_session()

        self._action_counter += 1
        action_id = f"{self._action_counter};a"

        action = {
            "id": action_id,
            "descriptor": descriptor,
            "callingDescriptor": calling_descriptor,
            "params": params or {},
        }
        if version:
            action["version"] = version
        else:
            action["version"] = None
        if storable:
            action["storable"] = True

        message = json.dumps({"actions": [action]})
        context = json.dumps({
            "mode": "PROD",
            "fwuid": AURA_FWUID,
            "app": "siteforce:communityApp",
            "loaded": {
                "APPLICATION@markup://siteforce:communityApp": AURA_APP_UID,
            },
            "dn": [],
            "globals": {},
            "uad": True,
        })

        payload = {
            "message": message,
            "aura.context": context,
            "aura.pageURI": "/s/",
            "aura.token": self._aura_token,
        }

        try:
            async with session.post(
                AURA_URL,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "*/*",
                    "Referer": f"{BASE_URL}/s/",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                },
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("[ReteleElectrice] Aura call HTTP %d", resp.status)
                    return None

                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    _LOGGER.error(
                        "[ReteleElectrice] Aura call: răspuns non-JSON (%s)",
                        text[:200],
                    )
                    return None

            actions = data.get("actions", [])
            if actions:
                action_result = actions[0]
                state = action_result.get("state", "UNKNOWN")
                if state == "SUCCESS":
                    return action_result.get("returnValue")
                else:
                    error = action_result.get("error", [])
                    _LOGGER.error(
                        "[ReteleElectrice] Aura action state=%s, error=%s",
                        state, error,
                    )
                    return {"state": state, "error": error}

            return data

        except Exception as e:
            _LOGGER.error("[ReteleElectrice] Aura call error: %s", e)
            return None

    # ===================================================================
    # A4J Response Parser
    # ===================================================================

    def _parse_a4j_response(self, response_text: str, method_name: str) -> Optional[Any]:
        """Parsează răspunsul A4J (partial page update) pentru a extrage datele WS."""
        # Metoda 1: Caută JSON direct în response
        json_patterns = [
            re.compile(r'\[(\{[^{]*?"sampleDate"[^]]*?\})\]'),
            re.compile(r'\[(\{[^{]*?"energyType"[^]]*?\})\]'),
            re.compile(r'(\{[^{]*?"errorCode"[^}]*?\})'),
            re.compile(r'(\{(?:[^{}]|\{[^{}]*\}){50,}\})'),
            re.compile(r'(\[(?:[^\[\]]|\[[^\[\]]*\]){50,}\])'),
        ]

        for pattern in json_patterns:
            match = pattern.search(response_text)
            if match:
                try:
                    data = json.loads(match.group(0))
                    return data
                except (json.JSONDecodeError, ValueError):
                    pass

        # Metoda 2: Caută în CDATA sections
        cdata_matches = re.findall(r'<!\[CDATA\[(.*?)\]\]>', response_text, re.DOTALL)
        for cdata in cdata_matches:
            try:
                data = json.loads(cdata.strip())
                return data
            except (json.JSONDecodeError, ValueError):
                pass

            json_match = re.search(r'[\[{].*[}\]]', cdata, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    return data
                except (json.JSONDecodeError, ValueError):
                    pass

        # Metoda 3: Caută result în span/div actualizat
        soup = BeautifulSoup(response_text, "html.parser")
        result_span = soup.find(id=re.compile(r"result", re.I))
        if result_span:
            text = result_span.get_text(strip=True)
            if text and len(text) > 5:
                try:
                    data = json.loads(text)
                    return data
                except (json.JSONDecodeError, ValueError):
                    if len(text) > 10:
                        return {"raw_result": text}

        # Metoda 4: Caută postMessage în script-uri
        pm_match = re.search(
            r'parent\.postMessage\s*\(\s*(\{[^}]+\})',
            response_text,
        )
        if pm_match:
            try:
                data = json.loads(pm_match.group(1))
                return data
            except (json.JSONDecodeError, ValueError):
                pass

        # Metoda 5: Extrage valori din input-uri actualizate
        inputs = soup.find_all("input")
        input_data = {}
        for inp in inputs:
            name = inp.get("name") or inp.get("id", "")
            value = inp.get("value", "")
            if value and name not in (
                "com.salesforce.visualforce.ViewState",
                "com.salesforce.visualforce.ViewStateVersion",
                "com.salesforce.visualforce.ViewStateMAC",
                "com.salesforce.visualforce.ViewStateCSRF",
            ):
                input_data[name] = value

        if input_data:
            return input_data

        return None

    # ===================================================================
    # HELPERS
    # ===================================================================

    def _extract_aura_token_from_cookies(self) -> Optional[str]:
        """Extrage aura token din cookie-ul __Host-ERIC_PROD*."""
        for cookie in self._cookie_jar:
            if cookie.key.startswith("__Host-ERIC_PROD"):
                return cookie.value
        return None

    def _extract_aura_token_from_html(self, html: str) -> Optional[str]:
        """Fallback: extrage aura token din HTML/JS."""
        jwt_match = re.search(r'jwt=(eyJ[A-Za-z0-9_-]+\.\.[A-Za-z0-9_-]+)', html)
        if jwt_match:
            return jwt_match.group(1)

        cookie_name_match = re.search(r'"eikoocnekot"\s*:\s*"([^"]+)"', html)
        if cookie_name_match:
            cookie_name = cookie_name_match.group(1)
            for cookie in self._cookie_jar:
                if cookie.key == cookie_name:
                    return cookie.value

        return None

    @staticmethod
    def _extract_field(soup: BeautifulSoup, field_name: str) -> Optional[str]:
        """Extrage o valoare dintr-un câmp input ascuns."""
        inp = soup.find("input", {"name": field_name})
        if inp:
            return inp.get("value", "")
        inp = soup.find("input", {"id": field_name})
        if inp:
            return inp.get("value", "")
        match = re.search(
            rf'name="{re.escape(field_name)}"[^>]*value="([^"]*)"', str(soup)
        )
        return match.group(1) if match else None

    @staticmethod
    def _find_input_name(soup: BeautifulSoup, candidates: list) -> str:
        """Găsește un câmp input după candidați."""
        for candidate in candidates:
            inp = soup.find("input", {"name": re.compile(candidate, re.I)})
            if inp:
                return inp.get("name", "")
            inp = soup.find("input", {"id": re.compile(candidate, re.I)})
            if inp:
                return inp.get("name") or inp.get("id", "")
        return f"loginPage:loginForm:{candidates[0]}"

    @staticmethod
    def _find_submit_name(soup: BeautifulSoup) -> str:
        """Găsește câmpul submit al formularului."""
        submit = soup.find("input", {"type": "submit"})
        if submit and submit.get("name"):
            return submit.get("name")
        for inp in soup.find_all("input"):
            name = inp.get("name", "")
            if "j_id" in name and inp.get("value") == name:
                return name
        return "loginPage:loginForm:j_id25"
