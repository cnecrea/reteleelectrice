"""
ConfigFlow și OptionsFlow pentru integrarea Rețele Electrice România.

Utilizatorul introduce email + parolă, apoi selectează POD-urile dorite.
Lista POD-urilor se descoperă automat prin Aura API.

OptionsFlow:
  - Meniu principal cu: Setări cont / Licență
  - Setări: modificare credențiale + interval + selecție POD-uri
  - Licență: activare / vizualizare licență (1:1 cu myelectrica)
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import ReteleElectriceAPI
from .const import CONF_LICENSE_KEY, DEFAULT_UPDATE, DOMAIN, LICENSE_DATA_KEY, LICENSE_PURCHASE_URL
from .helpers import build_pod_address, normalize_title

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_pod_options(pods: list[dict]) -> list[SelectOptionDict]:
    """Construiește lista de opțiuni pentru selectorul de POD-uri."""
    options: list[SelectOptionDict] = []

    for pod in pods:
        pod_name = pod.get("Name", "") or pod.get("POD__c", "")
        if not pod_name:
            continue

        # Adresa
        address = build_pod_address(pod)

        # Tip contract
        contract_type = pod.get("Contract_Type__c", "")
        smart_meter = pod.get("Smart_meter__c", False) or pod.get("IsSmartMeter__c", False)

        label = f"{address} ➜ POD: {pod_name}"
        if contract_type:
            label += f" ({contract_type})"
        if smart_meter:
            label += " "

        options.append(
            SelectOptionDict(value=pod_name, label=label)
        )

    return options


def _extract_all_pod_names(pods: list[dict]) -> list[str]:
    """Extrage toate numele POD-urilor unice."""
    names: list[str] = []
    for pod in pods:
        name = pod.get("Name", "") or pod.get("POD__c", "")
        if name and name not in names:
            names.append(name)
    return names


def _resolve_selected_pods(
    select_all: bool,
    selected: list[str],
    pods: list[dict],
) -> list[str]:
    """Returnează lista finală de POD-uri."""
    if select_all:
        return _extract_all_pod_names(pods)
    return selected


# ------------------------------------------------------------------
# ConfigFlow
# ------------------------------------------------------------------


class ReteleElectriceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow — autentificare + selecție POD-uri."""

    VERSION = 3

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE
        self._pods: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input["username"]
            self._password = user_input["password"]
            self._update_interval = user_input.get(
                "update_interval", DEFAULT_UPDATE
            )

            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            api = ReteleElectriceAPI(
                self.hass,
                username=self._username,
                password=self._password,
            )

            if await api.async_login():
                pods_raw = await api.async_get_pods()
                await api.async_close()

                if pods_raw and isinstance(pods_raw, list) and len(pods_raw) > 0:
                    self._pods = pods_raw
                    return await self.async_step_select_pod()

                errors["base"] = "no_data"
            else:
                await api.async_close()
                errors["base"] = "auth_failed"

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    "update_interval", default=DEFAULT_UPDATE
                ): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_select_pod(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            select_all = user_input.get("select_all", False)
            selected = user_input.get("selected_pods", [])

            if not select_all and not selected:
                errors["base"] = "no_pod_selected"
            else:
                final_selection = _resolve_selected_pods(
                    select_all, selected, self._pods
                )

                return self.async_create_entry(
                    title=f"Rețele Electrice ({self._username})",
                    data={
                        "username": self._username,
                        "password": self._password,
                        "update_interval": self._update_interval,
                        "select_all": select_all,
                        "selected_pods": final_selection,
                    },
                )

        pod_options = _build_pod_options(self._pods)

        schema = vol.Schema(
            {
                vol.Optional("select_all", default=False): bool,
                vol.Required("selected_pods", default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=pod_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_pod",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ReteleElectriceOptionsFlow:
        return ReteleElectriceOptionsFlow()


# ------------------------------------------------------------------
# OptionsFlow
# ------------------------------------------------------------------


class ReteleElectriceOptionsFlow(config_entries.OptionsFlow):
    """OptionsFlow — meniu cu setări cont și licențiere."""

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE
        self._pods: list[dict] = []

    # ─────────────────────────────────────────
    # Meniu principal
    # ─────────────────────────────────────────
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Afișează meniul principal cu opțiunile disponibile."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "settings",
                "licenta",
            ],
        )

    # ─────────────────────────────────────────
    # Setări cont (credențiale + interval + POD-uri)
    # ─────────────────────────────────────────
    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modificare credențiale și interval de actualizare."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]
            update_interval = user_input.get(
                "update_interval", DEFAULT_UPDATE
            )

            api = ReteleElectriceAPI(
                self.hass, username=username, password=password
            )

            if await api.async_login():
                pods_raw = await api.async_get_pods()
                await api.async_close()

                if pods_raw and isinstance(pods_raw, list) and len(pods_raw) > 0:
                    self._pods = pods_raw
                    self._username = username
                    self._password = password
                    self._update_interval = update_interval
                    return await self.async_step_select_pod()

                errors["base"] = "no_data"
            else:
                await api.async_close()
                errors["base"] = "auth_failed"

        current = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required(
                    "username", default=current.get("username", "")
                ): str,
                vol.Required(
                    "password", default=current.get("password", "")
                ): str,
                vol.Required(
                    "update_interval",
                    default=current.get(
                        "update_interval", DEFAULT_UPDATE
                    ),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="settings", data_schema=schema, errors=errors
        )

    async def async_step_select_pod(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modificare selecție POD-uri."""
        errors: dict[str, str] = {}

        if user_input is not None:
            select_all = user_input.get("select_all", False)
            selected = user_input.get("selected_pods", [])

            if not select_all and not selected:
                errors["base"] = "no_pod_selected"
            else:
                final_selection = _resolve_selected_pods(
                    select_all, selected, self._pods
                )

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        "username": self._username,
                        "password": self._password,
                        "update_interval": self._update_interval,
                        "select_all": select_all,
                        "selected_pods": final_selection,
                    },
                )

                await self.hass.config_entries.async_reload(
                    self.config_entry.entry_id
                )

                return self.async_create_entry(data={})

        current = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    "select_all",
                    default=current.get("select_all", False),
                ): bool,
                vol.Required(
                    "selected_pods",
                    default=current.get("selected_pods", []),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_build_pod_options(self._pods),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_pod",
            data_schema=schema,
            errors=errors,
        )

    # ─────────────────────────────────────────
    # Licențiere
    # ─────────────────────────────────────────
    async def async_step_licenta(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Formular pentru activarea / vizualizarea licenței Rețele Electrice."""
        from .license import LicenseManager

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        is_ro = self.hass.config.language == "ro"

        # Obține LicenseManager
        mgr: LicenseManager | None = self.hass.data.get(DOMAIN, {}).get(
            LICENSE_DATA_KEY
        )
        if mgr is None:
            mgr = LicenseManager(self.hass)
            await mgr.async_load()

        # Informații pentru descrierea formularului
        server_status = mgr.status

        if server_status == "licensed":
            from datetime import datetime

            tip = mgr.license_type or "necunoscut"
            status_lines = [f"✅ Licență activă ({tip})"]

            if mgr.license_key_masked:
                status_lines[0] += f" — {mgr.license_key_masked}"

            if mgr.activated_at:
                act_date = datetime.fromtimestamp(
                    mgr.activated_at
                ).strftime("%d.%m.%Y %H:%M")
                status_lines.append(f"Activată la: {act_date}")

            if mgr.license_expires_at:
                exp_date = datetime.fromtimestamp(
                    mgr.license_expires_at
                ).strftime("%d.%m.%Y %H:%M")
                status_lines.append(f"📅 Expiră la: {exp_date}")
            elif tip == "perpetual":
                status_lines.append("Valabilitate: nelimitată (perpetuă)")

            description_placeholders["license_status"] = "\n".join(
                status_lines
            )

        elif server_status == "trial":
            days = mgr.trial_days_remaining
            if is_ro:
                status_lines = [
                    f"⏳ Evaluare — {days} zile rămase",
                    "",
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}",
                ]
            else:
                status_lines = [
                    f"⏳ Trial — {days} days remaining",
                    "",
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}",
                ]
            description_placeholders["license_status"] = "\n".join(status_lines)
        elif server_status == "expired":
            from datetime import datetime

            status_lines = ["❌ Licență expirată"]

            if mgr.activated_at:
                act_date = datetime.fromtimestamp(
                    mgr.activated_at
                ).strftime("%d.%m.%Y")
                status_lines.append(f"Activată la: {act_date}")
            if mgr.license_expires_at:
                exp_date = datetime.fromtimestamp(
                    mgr.license_expires_at
                ).strftime("%d.%m.%Y")
                status_lines.append(f"Expirată la: {exp_date}")

            status_lines.append("")
            if is_ro:
                status_lines.append(
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}"
                )
            else:
                status_lines.append(
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}"
                )

            description_placeholders["license_status"] = "\n".join(
                status_lines
            )
        else:
            if is_ro:
                status_lines = [
                    "❌ Fără licență — funcționalitate blocată",
                    "",
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}",
                ]
            else:
                status_lines = [
                    "❌ No license — functionality blocked",
                    "",
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}",
                ]
            description_placeholders["license_status"] = "\n".join(status_lines)

        if user_input is not None:
            cheie = user_input.get(CONF_LICENSE_KEY, "").strip()

            if not cheie:
                errors["base"] = "license_key_empty"
            elif len(cheie) < 10:
                errors["base"] = "license_key_invalid"
            else:
                result = await mgr.async_activate(cheie)

                if result.get("success"):
                    from homeassistant.components import (
                        persistent_notification,
                    )

                    _LICENSE_TYPE_RO = {
                        "monthly": "lunară",
                        "yearly": "anuală",
                        "perpetual": "perpetuă",
                        "trial": "evaluare",
                    }
                    tip_ro = _LICENSE_TYPE_RO.get(
                        mgr.license_type, mgr.license_type or "necunoscut"
                    )

                    persistent_notification.async_create(
                        self.hass,
                        f"Licența Rețele Electrice a fost activată cu succes! "
                        f"Tip: {tip_ro}.",
                        title="Licență activată",
                        notification_id="reteleelectrice_license_activated",
                    )
                    return self.async_create_entry(
                        data=self.config_entry.options
                    )

                api_error = result.get("error", "unknown_error")
                error_map = {
                    "invalid_key": "license_key_invalid",
                    "already_used": "license_already_used",
                    "expired_key": "license_key_expired",
                    "fingerprint_mismatch": "license_fingerprint_mismatch",
                    "invalid_signature": "license_server_error",
                    "network_error": "license_network_error",
                    "server_error": "license_server_error",
                }
                errors["base"] = error_map.get(api_error, "license_server_error")

        schema = vol.Schema(
            {
                vol.Optional(CONF_LICENSE_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        suffix="RETE-XXXX-XXXX-XXXX-XXXX",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="licenta",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
