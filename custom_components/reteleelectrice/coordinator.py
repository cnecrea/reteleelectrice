"""
Coordinator pentru integrarea Rețele Electrice România.

Adună periodic datele de la API într-un singur dict (`self.data`)
pe care senzorii îl citesc fără a face request-uri directe.

Structura:
  Cont → POD-uri (puncte de consum)

Doar POD-urile selectate de utilizator sunt preluate.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import ReteleElectriceAPI
from .const import DEFAULT_UPDATE, DOMAIN

_LOGGER = logging.getLogger(__name__)

type ReteleElectriceConfigEntry = ConfigEntry["ReteleElectriceCoordinator"]


class ReteleElectriceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Coordinator central.

    `self.data` conține:
    {
        "user_name":         str,                   # Numele utilizatorului
        "account_info":      dict,                  # Informații cont (CNP, adresă, etc.)
        "contact_info":      dict,                  # Informații contact
        "pods":              list[dict],             # Lista POD-urilor raw
        "pod_details":       {pod: dict},            # Detalii per POD (Aura)
        "pod_reading_details": {pod: dict},          # Detalii citire per POD
        "reading_archive":   {pod: dict},            # Istoric citiri per POD (VF)
        "power_outages":     {pod: dict},            # Întreruperi per POD (VF)
        "smart_meter":       {pod: dict},            # Date smart meter per POD (VF)
        "instant_values":    {pod: dict},            # Valoare instantanee per POD (VF)
        "supplier_data":     {pod: dict},            # Date furnizor per POD (VF — queryPOD)
        "selected_pods":     list[str],              # POD-urile selectate
    }
    """

    config_entry: ReteleElectriceConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        update_seconds = config_entry.data.get("update_interval", DEFAULT_UPDATE)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_seconds),
            config_entry=config_entry,
        )

        self.api = ReteleElectriceAPI(
            hass,
            username=config_entry.data["username"],
            password=config_entry.data["password"],
        )

        # POD-urile selectate de utilizator (None = toate)
        self._selected_pods: list[str] | None = config_entry.data.get(
            "selected_pods"
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch periodic — colectează datele pentru POD-urile selectate."""
        _LOGGER.debug("[ReteleElectrice] Începe actualizarea datelor")

        try:
            # ── Login (dacă sesiunea a expirat) ──
            if not self.api._logged_in:
                if not await self.api.async_login():
                    raise UpdateFailed("Nu s-a putut autentifica la Rețele Electrice")

            # ── Date cont (Aura) ──
            user_name = await self.api.async_get_user_name()
            account_info = await self.api.async_get_account_info()
            contact_info = await self.api.async_get_contact_info()

            # ── Lista POD-uri ──
            pods_raw = await self.api.async_get_pods()
            if not pods_raw or not isinstance(pods_raw, list):
                # Posibil sesiune expirată — re-login
                _LOGGER.warning("[ReteleElectrice] POD-uri goale — reîncerc login...")
                if await self.api.async_login():
                    pods_raw = await self.api.async_get_pods()

                if not pods_raw or not isinstance(pods_raw, list):
                    raise UpdateFailed("Nu s-au putut obține POD-urile")

            # Filtrare POD-uri selectate
            if self._selected_pods:
                filtered_pods = [
                    pod for pod in pods_raw
                    if (pod.get("Name") or pod.get("POD__c", "")) in self._selected_pods
                ]
            else:
                filtered_pods = pods_raw

            _LOGGER.debug(
                "[ReteleElectrice] %d POD-uri descoperite, %d selectate",
                len(pods_raw),
                len(filtered_pods),
            )

            # Extrage CNP din account_info (necesar pt VF calls)
            cnp = ""
            if account_info and isinstance(account_info, dict):
                cnp = account_info.get("CNP__c", "") or account_info.get("Fiscal_Code__c", "")

            # ── Date per POD ──
            pod_details: dict[str, Any] = {}
            pod_reading_details: dict[str, Any] = {}
            reading_archive: dict[str, Any] = {}
            power_outages: dict[str, Any] = {}
            smart_meter: dict[str, Any] = {}
            instant_values: dict[str, Any] = {}
            supplier_data: dict[str, Any] = {}

            for pod in filtered_pods:
                pod_name = pod.get("Name") or pod.get("POD__c", "")
                if not pod_name:
                    continue

                # Detalii POD (Aura)
                pod_details[pod_name] = await self.api.async_get_pod_details(pod_name)

                # Detalii citire POD
                pod_reading_details[pod_name] = await self.api.async_get_reading_archive_pod_details(pod_name)

                # Istoric citiri (VF — RetriveSingleSelf)
                reading_archive[pod_name] = await self.api.async_get_reading_archive(
                    pod_name, cnp=cnp
                )

                # Întreruperi (VF — PowerOutages)
                power_outages[pod_name] = await self.api.async_get_power_outages(pod_name)

                # Smart meter (VF — FindOutMeterHistoryData)
                is_smart = pod.get("Smart_meter__c", False) or pod.get("IsSmartMeter__c", False)
                if is_smart:
                    smart_meter[pod_name] = await self.api.async_get_smart_meter_data(
                        pod_name, cnp=cnp
                    )

                    # Valoare instantanee (VF — ReqMeterInstantData + FindOutMeterInstantData)
                    instant_values[pod_name] = await self.api.async_get_instant_values(
                        pod_name, cnp=cnp
                    )

                # Date furnizor (VF — queryPOD)
                supplier_data[pod_name] = await self.api.async_get_supplier_data(pod_name)

        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("[ReteleElectrice] Eroare la actualizare: %s", err)
            raise UpdateFailed(f"Eroare la actualizarea datelor: {err}") from err

        data: dict[str, Any] = {
            "user_name": user_name,
            "account_info": account_info,
            "contact_info": contact_info,
            "pods": filtered_pods,
            "pod_details": pod_details,
            "pod_reading_details": pod_reading_details,
            "reading_archive": reading_archive,
            "power_outages": power_outages,
            "smart_meter": smart_meter,
            "instant_values": instant_values,
            "supplier_data": supplier_data,
            "selected_pods": self._selected_pods,
        }

        _LOGGER.debug("[ReteleElectrice] Actualizare completă")
        return data
