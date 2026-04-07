"""
Platforma Button pentru Rețele Electrice România.

Creează un buton per POD (smart meter) pentru a forța
actualizarea valorilor instantanee de la contor.
"""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, LICENSE_DATA_KEY
from .coordinator import ReteleElectriceCoordinator
from .helpers import build_pod_address

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurare butoane: un buton per POD smart meter."""
    coordinator: ReteleElectriceCoordinator = config_entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("[ReteleElectrice] Button: coordinator.data este gol")
        return

    pods = coordinator.data.get("pods", [])
    selected = coordinator.data.get("selected_pods", [])
    account_name = ""
    account = coordinator.data.get("account_info")
    if account and isinstance(account, dict):
        account_name = account.get("Name", "")

    entities: list[ButtonEntity] = []

    for pod in pods:
        pod_name = pod.get("Name") or pod.get("POD__c", "")
        if not pod_name or pod_name not in selected:
            continue

        is_smart = pod.get("Smart_meter__c", False) or pod.get(
            "IsSmartMeter__c", False
        )

        if not is_smart:
            continue

        address = build_pod_address(pod)

        entities.append(
            ActualizareInstantaneeButton(
                coordinator, config_entry, pod_name, pod, account_name, address
            )
        )

    _LOGGER.debug(
        "[ReteleElectrice] Se adaugă %d butoane (entry_id=%s)",
        len(entities),
        config_entry.entry_id,
    )

    async_add_entities(entities)


class ActualizareInstantaneeButton(
    CoordinatorEntity[ReteleElectriceCoordinator], ButtonEntity
):
    """Buton pentru forțarea actualizării valorilor instantanee."""

    _attr_has_entity_name = True
    _attr_translation_key = "actualizare_instantanee"
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: ReteleElectriceCoordinator,
        config_entry: ConfigEntry,
        pod_name: str,
        pod_data: dict,
        account_name: str,
        address: str,
    ) -> None:
        """Inițializare buton actualizare instantanee."""
        super().__init__(coordinator)
        self._pod_name = pod_name
        self._pod_data = pod_data
        self._config_entry = config_entry
        self._account_name = account_name
        self._address = address
        self._attr_unique_id = f"{DOMAIN}_{pod_name.lower()}_actualizare_instantanee"

    @property
    def device_info(self) -> DeviceInfo:
        """Asociere la device-ul POD-ului."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._pod_name)},
            name=f"Rețele Electrice {self._pod_name}",
            manufacturer="Ciprian Nicolae (cnecrea)",
            model="Rețele Electrice România",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _is_license_valid(self) -> bool:
        """Verifică dacă licența este validă."""
        mgr = self.hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
        return mgr is not None and mgr.is_valid

    async def async_press(self) -> None:
        """Acțiune la apăsarea butonului: forțează actualizare valori instantanee."""
        if not self._is_license_valid():
            _LOGGER.warning(
                "[ReteleElectrice] Buton blocat: licența nu este validă (POD %s)",
                self._pod_name,
            )
            return

        _LOGGER.info(
            "[ReteleElectrice] Buton apăsat: actualizare instantanee pentru POD %s",
            self._pod_name,
        )

        # Obținem CNP din datele contului
        cnp = ""
        account = self.coordinator.data.get("account_info")
        if account and isinstance(account, dict):
            cnp = account.get("CNP__c", "") or account.get("Fiscal_Code__c", "")

        try:
            result = await self.coordinator.api.async_get_instant_values(
                self._pod_name, cnp=cnp
            )

            # Actualizăm datele din coordinator
            if self.coordinator.data and result:
                instant = self.coordinator.data.get("instant_values", {})
                instant[self._pod_name] = result
                self.coordinator.data["instant_values"] = instant

                # Notificăm toate entitățile să se actualizeze
                self.coordinator.async_set_updated_data(self.coordinator.data)

                _LOGGER.debug(
                    "[ReteleElectrice] Valori instantanee actualizate cu succes pentru POD %s",
                    self._pod_name,
                )
        except Exception as err:
            _LOGGER.error(
                "[ReteleElectrice] Eroare la actualizarea valorilor instantanee pentru POD %s: %s",
                self._pod_name,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict:
        """Atribute suplimentare."""
        return {
            "POD": self._pod_name,
            "attribution": ATTRIBUTION,
        }
