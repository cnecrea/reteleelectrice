"""
Platforma Sensor pentru Rețele Electrice România.

Creează câte un device per POD (punct de consum) selectat,
cu senzori separați pentru energie consumată și energie produsă:

  1.  Informații POD                     — date contract, tip, putere, adresă
  2.  Informații cont                    — CNP, email, telefon, adresă
  3.  Index citire consum                — ultimul index contor consum (kWh, Energy dashboard)
  4.  Index citire producție             — ultimul index contor producție (kWh, doar prosumer)
  5.  Arhivă energie consumată {an}      — citiri consum grupate pe an (maxim 2 ani)
  6.  Arhivă energie produsă {an}        — citiri producție grupate pe an (doar prosumer)
  7.  Întreruperi curent                 — status PowerOutages
  8.  Smart Meter Consum                 — total energie consumată smart meter (kWh)
  9.  Smart Meter Producție              — total energie produsă smart meter (kWh, doar prosumer)
 10.  Date furnizor                      — furnizor, PRE, CUI, date tehnice POD, contor
 11.  Valoare instantanee consum         — energie activă consumată instantanee (kWh, smart meter)
 12.  Valoare instantanee producție      — energie activă produsă instantanee (kWh, smart meter, prosumer)
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, LICENSE_DATA_KEY
from .coordinator import ReteleElectriceCoordinator
from .helpers import (
    build_pod_address,
    decode_html_entities,
    format_date_ro_ddmmyyyy,
    normalize_title,
    safe_float,
)

_LOGGER = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────


@dataclass
class PodContext:
    """Context pentru un POD (partajat între senzori)."""

    pod_name: str
    pod_data: dict
    account_name: str
    address: str
    is_prosumer: bool
    is_smart: bool


def _is_license_valid(hass: HomeAssistant) -> bool:
    """Verifică dacă licența este validă."""
    mgr = hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
    return mgr is not None and mgr.is_valid


def _get_readings_from_coordinator(data: dict, pod_name: str) -> list:
    """Extrage citirile din coordinator data."""
    if not data:
        return []
    archive = data.get("reading_archive", {}).get(pod_name)
    if not archive or not isinstance(archive, dict):
        return []
    return archive.get("XML_Readings", [])


def _extract_years_from_readings(readings: list[dict]) -> list[int]:
    """Extrage anii unici din citiri, sortați descrescător, maxim 2."""
    years: set[int] = set()
    for r in readings:
        date_str = r.get("measureDate", "")
        try:
            parsed = datetime.strptime(date_str.split(" ")[0], "%d.%m.%Y")
            years.add(parsed.year)
        except (ValueError, TypeError):
            pass
    return sorted(years, reverse=True)[:2]


def _filter_readings_by_year(readings: list[dict], year: int) -> list[dict]:
    """Filtrează citirile pentru un an specific."""
    result: list[dict] = []
    for r in readings:
        date_str = r.get("measureDate", "")
        try:
            parsed = datetime.strptime(date_str.split(" ")[0], "%d.%m.%Y")
            if parsed.year == year:
                result.append(r)
        except (ValueError, TypeError):
            pass
    return result


def _get_energy_value(meters: list[dict], energy_type: str) -> float | None:
    """Extrage valoarea numerică pentru un tip de energie (EA/EAP) din lista meter."""
    for m in meters:
        if m.get("typeofenergy_measured") == energy_type:
            return safe_float(m.get("Value"), None)
    return None


def _format_reading_date(date_str: str) -> str:
    """Formatează data citire din DD.MM.YYYY → '1 decembrie 2025'."""
    return format_date_ro_ddmmyyyy(date_str)


# ── async_setup_entry ────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurează senzorii pe baza POD-urilor descoperite."""
    coordinator: ReteleElectriceCoordinator = config_entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("[ReteleElectrice] Coordinator fără date la setup sensors")
        return

    pods = coordinator.data.get("pods", [])
    if not isinstance(pods, list):
        _LOGGER.warning("[ReteleElectrice] Formatul POD-urilor este invalid")
        return

    account_info = coordinator.data.get("account_info") or {}
    raw_name = (
        account_info.get("Name", "Necunoscut")
        if isinstance(account_info, dict)
        else "Necunoscut"
    )
    account_name = normalize_title(raw_name)

    entities: list[SensorEntity] = []

    for pod in pods:
        pod_name = pod.get("Name") or pod.get("POD__c", "")
        if not pod_name:
            continue

        address = build_pod_address(pod)
        is_prosumer = pod.get("isProductor__c", False) or (
            (pod.get("Contract_Type__c", "") or "").upper() == "PROSUMER"
        )
        is_smart = pod.get("Smart_meter__c", False) or pod.get(
            "IsSmartMeter__c", False
        )

        ctx = PodContext(
            pod_name=pod_name,
            pod_data=pod,
            account_name=account_name,
            address=address,
            is_prosumer=is_prosumer,
            is_smart=is_smart,
        )

        # ── Senzori generali ──
        entities.append(InformatiiPodSensor(coordinator, config_entry, ctx))
        entities.append(InformatiiContSensor(coordinator, config_entry, ctx))
        entities.append(IntreruperiCurentSensor(coordinator, config_entry, ctx))

        # ── Index citire consum / producție ──
        entities.append(IndexCitireConsumSensor(coordinator, config_entry, ctx))
        if is_prosumer:
            entities.append(IndexCitireProductieSensor(coordinator, config_entry, ctx))

        # ── Arhivă energie consumată / produsă per an (maxim 2 ani) ──
        readings = _get_readings_from_coordinator(coordinator.data, pod_name)
        years = _extract_years_from_readings(readings)
        for year in years:
            entities.append(
                ArhivaEnergieConsumataSensor(coordinator, config_entry, ctx, year)
            )
            if is_prosumer:
                entities.append(
                    ArhivaEnergieProdusSensor(coordinator, config_entry, ctx, year)
                )

        # ── Date furnizor (queryPOD) ──
        entities.append(DateFurnizorSensor(coordinator, config_entry, ctx))

        # ── Smart Meter Consum / Producție (doar smart meter) ──
        if is_smart:
            entities.append(SmartMeterConsumSensor(coordinator, config_entry, ctx))
            if is_prosumer:
                entities.append(SmartMeterProductieSensor(coordinator, config_entry, ctx))

            # ── Valoare instantanee Consum / Producție (doar smart meter) ──
            entities.append(ValoareInstantaneeConsumSensor(coordinator, config_entry, ctx))
            if is_prosumer:
                entities.append(ValoareInstantaneeProductieSensor(coordinator, config_entry, ctx))

    _LOGGER.debug(
        "[ReteleElectrice] Se adaugă %d senzori (entry_id=%s)",
        len(entities),
        config_entry.entry_id,
    )

    async_add_entities(entities)


# ── Base Sensor ──────────────────────────────────


class ReteleElectriceSensorBase(
    CoordinatorEntity[ReteleElectriceCoordinator], SensorEntity
):
    """Clasa de bază pentru toți senzorii Rețele Electrice."""

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: ReteleElectriceCoordinator,
        config_entry: ConfigEntry,
        ctx: PodContext,
        sensor_key: str,
        sensor_name: str,
        icon: str = "mdi:flash",
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._ctx = ctx
        self._sensor_key = sensor_key
        self._attr_name = sensor_name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{ctx.pod_name}_{sensor_key}"
        self._custom_entity_id = (
            f"sensor.{DOMAIN}_{ctx.pod_name}_{sensor_key}"
        )

    @property
    def entity_id(self) -> str | None:
        return self._custom_entity_id

    @entity_id.setter
    def entity_id(self, value: str) -> None:
        self._custom_entity_id = value

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ctx.pod_name)},
            name=f"Rețele Electrice {self._ctx.pod_name}",
            manufacturer="Ciprian Nicolae (cnecrea)",
            model="Rețele Electrice România",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Senzorul e disponibil dacă coordinator-ul are date."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )


# ══════════════════════════════════════════════════
# 1. Informații POD
# ══════════════════════════════════════════════════


class InformatiiPodSensor(ReteleElectriceSensorBase):
    """Senzor cu informațiile POD-ului (contract, putere, tip, contor)."""

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="informatii_pod",
            sensor_name="POD",
            icon="mdi:file-document-outline",
        )

    @property
    def native_value(self) -> str | None:
        if not _is_license_valid(self.hass):
            return "Licență necesară"
        pod = self._ctx.pod_data
        return normalize_title(pod.get("Contract_Type__c", "Necunoscut"))

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        pod = self._ctx.pod_data
        return {
            "POD": self._ctx.pod_name,
            "Adresă": self._ctx.address,
            "Tip contract": normalize_title(
                pod.get("Contract_Type__c", "")
            ),
            "Stare contract": normalize_title(
                pod.get("Contract_State__c", "")
            ),
            "Tip consumator": normalize_title(
                pod.get("Consumer_Type_Account__c", "")
            ),
            "Piață": normalize_title(pod.get("Market_Type__c", "")),
            "Putere absorbită (kW)": pod.get("Absorbed_Power_KW__c", ""),
            "Putere absorbită (kVA)": pod.get("Absorbed_Power_KVA__c", ""),
            "Putere cedată (kW)": pod.get("Released_Power_KW__c", ""),
            "Putere cedată (kVA)": pod.get("Released_Power_KVA__c", ""),
            "Nivel tensiune": pod.get("Voltage_Level__c", ""),
            "Tensiune nominală (kV)": pod.get("Nominal_Voltage_kV__c", ""),
            "Serie contor": pod.get("EA_METER_SERIE__c", ""),
            "Tip contor": pod.get("EA_METER_TYPE__c", ""),
            "Smart meter": self._ctx.is_smart,
            "Prosumer": self._ctx.is_prosumer,
            "Tarif": pod.get("TARIFF__c", ""),
            "Profil consum": pod.get("ConsumptionProfile__c", ""),
            "Constantă contor": pod.get("EA_CONSTANT__c", ""),
            "Precizie": pod.get("EA_PRECISION__c", ""),
            "Unitate operativă": pod.get("Operative_Unit__c", ""),
            "Zonă": pod.get("Zone_Cod__c", ""),
            "Cod CFT": pod.get("CFT_Code__c", ""),
            "ATR": pod.get("ATR__c", ""),
            "Perioadă măsurare": pod.get("MeasurementPeriod__c", ""),
            "Dată start contract": pod.get("ContractStartDate__c", ""),
            "Distribuitor": normalize_title(
                (pod.get("DistributionCompany__r") or {}).get("Name", "")
            ),
            "attribution": ATTRIBUTION,
        }


# ══════════════════════════════════════════════════
# 2. Informații cont
# ══════════════════════════════════════════════════


class InformatiiContSensor(ReteleElectriceSensorBase):
    """Senzor cu informațiile contului (CNP, email, adresă)."""

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="informatii_cont",
            sensor_name="Date utilizator",
            icon="mdi:account-circle",
        )

    @property
    def native_value(self) -> str | None:
        if not _is_license_valid(self.hass):
            return "Licență necesară"
        return self._ctx.account_name

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        account = self.coordinator.data.get("account_info") or {}
        contact = self.coordinator.data.get("contact_info") or {}

        if not isinstance(account, dict):
            account = {}
        if not isinstance(contact, dict):
            contact = {}

        return {
            "Nume": normalize_title(account.get("Name", "")),
            "Email": account.get("Email__c", "")
            or contact.get("Email", ""),
            "Telefon": account.get("Mobile_Phone__c", "")
            or contact.get("MobilePhone", ""),
            "CNP": account.get("CNP__c", ""),
            "Cod fiscal": account.get("Fiscal_Code__c", ""),
            "Adresă": normalize_title(account.get("Address__c", "")),
            "Oraș": normalize_title(account.get("City__c", "")),
            "Județ": normalize_title(account.get("County__c", "")),
            "Cod poștal": account.get("ZIP_COD__c", ""),
            "Tip cont": normalize_title(
                (account.get("RecordType") or {}).get("Name", "")
            ),
            "attribution": ATTRIBUTION,
        }


# ══════════════════════════════════════════════════
# 3. Index citire consum (energie consumată)
# ══════════════════════════════════════════════════


class IndexCitireConsumSensor(ReteleElectriceSensorBase):
    """Index contor energie consumată — compatibil Energy dashboard.

    Valoarea este indexul contorului (kWh, TOTAL_INCREASING),
    cu consum lunar calculat în atribute.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="index_citire_consum",
            sensor_name="Index citire consum",
            icon="mdi:counter",
        )

    @property
    def native_value(self) -> float | None:
        if not _is_license_valid(self.hass):
            return None

        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        if not readings:
            return None

        latest = readings[0]
        return _get_energy_value(latest.get("meter", []), "EA")

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        if not readings:
            return {"attribution": ATTRIBUTION}

        latest = readings[0]
        ea_val = _get_energy_value(latest.get("meter", []), "EA")

        attrs: dict = {
            "Data citire": _format_reading_date(latest.get("measureDate", "")),
            "Tip citire": normalize_title(latest.get("typeOfReading", "")),
            "Serie contor": latest.get("SerialNumber", ""),
            "Constantă": latest.get("constanta", ""),
            "Index energie consumată (kWh)": ea_val,
        }

        # Consum lunar (diferența față de citirea anterioară)
        if len(readings) >= 2:
            prev = readings[1]
            prev_ea = _get_energy_value(prev.get("meter", []), "EA")
            if ea_val is not None and prev_ea is not None:
                attrs["Consum lunar (kWh)"] = round(ea_val - prev_ea, 3)
                attrs["Citire anterioară"] = _format_reading_date(
                    prev.get("measureDate", "")
                )

        attrs["attribution"] = ATTRIBUTION
        return attrs


# ══════════════════════════════════════════════════
# 4. Index citire producție (energie produsă)
# ══════════════════════════════════════════════════


class IndexCitireProductieSensor(ReteleElectriceSensorBase):
    """Index contor energie produsă — compatibil Energy dashboard.

    Doar pentru POD-uri de tip prosumer.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="index_citire_productie",
            sensor_name="Index citire producție",
            icon="mdi:solar-power",
        )

    @property
    def native_value(self) -> float | None:
        if not _is_license_valid(self.hass):
            return None

        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        if not readings:
            return None

        latest = readings[0]
        return _get_energy_value(latest.get("meter", []), "EAP")

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        if not readings:
            return {"attribution": ATTRIBUTION}

        latest = readings[0]
        eap_val = _get_energy_value(latest.get("meter", []), "EAP")

        attrs: dict = {
            "Data citire": _format_reading_date(latest.get("measureDate", "")),
            "Tip citire": normalize_title(latest.get("typeOfReading", "")),
            "Serie contor": latest.get("SerialNumber", ""),
            "Constantă": latest.get("constanta", ""),
            "Index energie produsă (kWh)": eap_val,
        }

        # Producție lunară
        if len(readings) >= 2:
            prev = readings[1]
            prev_eap = _get_energy_value(prev.get("meter", []), "EAP")
            if eap_val is not None and prev_eap is not None:
                attrs["Producție lunară (kWh)"] = round(
                    eap_val - prev_eap, 3
                )
                attrs["Citire anterioară"] = _format_reading_date(
                    prev.get("measureDate", "")
                )

        attrs["attribution"] = ATTRIBUTION
        return attrs


# ══════════════════════════════════════════════════
# 5. Arhivă energie consumată per an
# ══════════════════════════════════════════════════


class ArhivaEnergieConsumataSensor(ReteleElectriceSensorBase):
    """Arhiva energiei consumate pentru un an specific.

    native_value = consumul total pe an (kWh).
    Atributele conțin fiecare citire lunară cu data formatată în română.
    """

    def __init__(
        self,
        coordinator,
        config_entry,
        ctx: PodContext,
        year: int,
    ) -> None:
        self._year = year
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key=f"arhiva_energie_consumata_{year}",
            sensor_name=f"{year} → Energie consumată",
            icon="mdi:history",
        )

    @property
    def native_value(self) -> str | None:
        if not _is_license_valid(self.hass):
            return "Licență necesară"

        year_readings = self._get_year_readings()
        if not year_readings:
            return "Fără date"

        # Consum total an = ultima citire − prima citire din an
        first_ea = _get_energy_value(
            year_readings[-1].get("meter", []), "EA"
        )
        last_ea = _get_energy_value(
            year_readings[0].get("meter", []), "EA"
        )

        if first_ea is not None and last_ea is not None and len(year_readings) > 1:
            total = round(last_ea - first_ea, 3)
            return f"{total} kWh"

        # O singură citire → arătăm valoarea directă
        if year_readings:
            ea = _get_energy_value(year_readings[0].get("meter", []), "EA")
            if ea is not None:
                return f"{ea} kWh"

        return "Fără date"

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        year_readings = self._get_year_readings()
        if not year_readings:
            return {"attribution": ATTRIBUTION}

        attrs: dict = {}
        for reading in year_readings:
            date_str = reading.get("measureDate", "")
            date_label = _format_reading_date(date_str)
            ea_val = _get_energy_value(reading.get("meter", []), "EA")
            attrs[date_label] = (
                f"{ea_val} kWh" if ea_val is not None else "fără date"
            )

        attrs["Total citiri"] = len(year_readings)
        attrs["Serie contor"] = (
            year_readings[0].get("SerialNumber", "") if year_readings else ""
        )
        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_year_readings(self) -> list[dict]:
        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        return _filter_readings_by_year(readings, self._year)


# ══════════════════════════════════════════════════
# 6. Arhivă energie produsă per an
# ══════════════════════════════════════════════════


class ArhivaEnergieProdusSensor(ReteleElectriceSensorBase):
    """Arhiva energiei produse pentru un an specific.

    Doar pentru POD-uri de tip prosumer.
    """

    def __init__(
        self,
        coordinator,
        config_entry,
        ctx: PodContext,
        year: int,
    ) -> None:
        self._year = year
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key=f"arhiva_energie_produsa_{year}",
            sensor_name=f"{year} → Energie produsă",
            icon="mdi:solar-power",
        )

    @property
    def native_value(self) -> str | None:
        if not _is_license_valid(self.hass):
            return "Licență necesară"

        year_readings = self._get_year_readings()
        if not year_readings:
            return "Fără date"

        first_eap = _get_energy_value(
            year_readings[-1].get("meter", []), "EAP"
        )
        last_eap = _get_energy_value(
            year_readings[0].get("meter", []), "EAP"
        )

        if first_eap is not None and last_eap is not None and len(year_readings) > 1:
            total = round(last_eap - first_eap, 3)
            return f"{total} kWh"

        if year_readings:
            eap = _get_energy_value(year_readings[0].get("meter", []), "EAP")
            if eap is not None:
                return f"{eap} kWh"

        return "Fără date"

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        year_readings = self._get_year_readings()
        if not year_readings:
            return {"attribution": ATTRIBUTION}

        attrs: dict = {}
        for reading in year_readings:
            date_str = reading.get("measureDate", "")
            date_label = _format_reading_date(date_str)
            eap_val = _get_energy_value(reading.get("meter", []), "EAP")
            attrs[date_label] = (
                f"{eap_val} kWh" if eap_val is not None else "fără date"
            )

        attrs["Total citiri"] = len(year_readings)
        attrs["Serie contor"] = (
            year_readings[0].get("SerialNumber", "") if year_readings else ""
        )
        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_year_readings(self) -> list[dict]:
        readings = _get_readings_from_coordinator(
            self.coordinator.data, self._ctx.pod_name
        )
        return _filter_readings_by_year(readings, self._year)


# ══════════════════════════════════════════════════
# 7. Întreruperi curent
# ══════════════════════════════════════════════════


class IntreruperiCurentSensor(ReteleElectriceSensorBase):
    """Senzor cu informații despre întreruperile de curent."""

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="intreruperi_curent",
            sensor_name="Întreruperi curent",
            icon="mdi:flash-alert",
        )

    @property
    def native_value(self) -> str | None:
        if not _is_license_valid(self.hass):
            return "Licență necesară"

        outage_data = self._get_outage_data()
        if not outage_data:
            return "Fără date"

        data_obj = outage_data.get("data")
        if isinstance(data_obj, dict):
            check = data_obj.get("checkInterruzione", "")
            if check == "true":
                return "Fără întreruperi"
            elif check == "false":
                return "Întrerupere activă"

        esito = outage_data.get("esito", "")
        return esito or "Necunoscut"

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        outage_data = self._get_outage_data()
        if not outage_data:
            return {"attribution": ATTRIBUTION}

        attrs: dict = {"POD": self._ctx.pod_name}

        data_obj = outage_data.get("data")
        if isinstance(data_obj, dict):
            messaggio = data_obj.get("messaggio", "")
            if messaggio:
                attrs["Mesaj"] = decode_html_entities(messaggio)
            attrs["Verificare întreruperi"] = data_obj.get(
                "checkInterruzione", ""
            )
            attrs["Rezultat"] = data_obj.get("esito", "")

        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_outage_data(self) -> dict | None:
        if not self.coordinator.data:
            return None
        return (
            self.coordinator.data.get("power_outages", {}).get(
                self._ctx.pod_name
            )
        )


# ══════════════════════════════════════════════════
# 8. Smart Meter Consum (energie consumată)
# ══════════════════════════════════════════════════


class SmartMeterConsumSensor(ReteleElectriceSensorBase):
    """Total energie consumată de la smart meter (FindOutMeterHistoryData).

    Compatibil Energy dashboard (device_class=ENERGY, state_class=TOTAL).
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="smart_meter_consum",
            sensor_name="Smart Meter Consum",
            icon="mdi:chart-line",
        )

    @property
    def native_value(self) -> float | None:
        if not _is_license_valid(self.hass):
            return None

        sm_data = self._get_smart_meter_data()
        if not sm_data:
            return None

        if sm_data.get("Result", "") != "OK":
            return None

        rows = sm_data.get("row", [])
        if not rows:
            return None

        return safe_float(rows[0].get("SUM_EA", "0"), None)

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        sm_data = self._get_smart_meter_data()
        if not sm_data:
            return {"attribution": ATTRIBUTION}

        rows = sm_data.get("row", [])
        if not rows:
            return {
                "Rezultat": sm_data.get("Result", ""),
                "attribution": ATTRIBUTION,
            }

        row = rows[0]

        attrs: dict = {
            "POD": row.get("POD", self._ctx.pod_name),
            "Contor": row.get("METER", ""),
            "Perioadă start": row.get("START_DATE", ""),
            "Perioadă sfârșit": row.get("END_DATE", ""),
            "Total energie consumată (kWh)": safe_float(row.get("SUM_EA", "0")),
            "Vârf consum (kWh)": safe_float(row.get("MAX_EA", "0")),
        }

        # Energie reactivă (dacă disponibilă)
        sum_er = row.get("SUM_ER", "")
        if sum_er:
            attrs["Total energie reactivă (kVArh)"] = safe_float(sum_er)
        max_er = row.get("MAX_ER", "")
        if max_er:
            attrs["Vârf energie reactivă (kVArh)"] = safe_float(max_er)

        # Factor de putere inductiv
        cosfi = row.get("COSFI", "-9999")
        if cosfi and cosfi != "-9999":
            attrs["Factor de putere (cosφ)"] = safe_float(cosfi)

        attrs["Rezultat"] = sm_data.get("Result", "")
        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_smart_meter_data(self) -> dict | None:
        if not self.coordinator.data:
            return None
        return (
            self.coordinator.data.get("smart_meter", {}).get(
                self._ctx.pod_name
            )
        )


# ══════════════════════════════════════════════════
# 9. Smart Meter Producție (energie produsă)
# ══════════════════════════════════════════════════


class SmartMeterProductieSensor(ReteleElectriceSensorBase):
    """Total energie produsă de la smart meter (FindOutMeterHistoryData).

    Doar pentru POD-uri de tip prosumer.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator, config_entry, ctx: PodContext) -> None:
        super().__init__(
            coordinator,
            config_entry,
            ctx,
            sensor_key="smart_meter_productie",
            sensor_name="Smart Meter Producție",
            icon="mdi:solar-power",
        )

    @property
    def native_value(self) -> float | None:
        if not _is_license_valid(self.hass):
            return None

        sm_data = self._get_smart_meter_data()
        if not sm_data:
            return None

        if sm_data.get("Result", "") != "OK":
            return None

        rows = sm_data.get("row", [])
        if not rows:
            return None

        return safe_float(rows[0].get("SUM_EAP", "0"), None)

    @property
    def extra_state_attributes(self) -> dict:
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}

        sm_data = self._get_smart_meter_data()
        if not sm_data:
            return {"attribution": ATTRIBUTION}

        rows = sm_data.get("row", [])
        if not rows:
            return {
                "Rezultat": sm_data.get("Result", ""),
                "attribution": ATTRIBUTION,
            }

        row = rows[0]

        attrs: dict = {
            "POD": row.get("POD", self._ctx.pod_name),
            "Contor": row.get("METER", ""),
            "Perioadă start": row.get("START_DATE", ""),
            "Perioadă sfârșit": row.get("END_DATE", ""),
            "Total energie produsă (kWh)": safe_float(row.get("SUM_EAP", "0")),
            "Vârf producție (kWh)": safe_float(row.get("MAX_EAP", "0")),
        }

        # Energie reactivă capacitivă (dacă disponibilă)
        sum_erc = row.get("SUM_ERC", "")
        if sum_erc:
            attrs["Total energie reactivă capacitivă (kVArh)"] = safe_float(sum_erc)
        max_erc = row.get("MAX_ERC", "")
        if max_erc:
            attrs["Vârf energie reactivă capacitivă (kVArh)"] = safe_float(max_erc)

        # Factor de putere capacitiv
        cosfic = row.get("COSFIC", "-9999")
        if cosfic and cosfic != "-9999":
            attrs["Factor de putere capacitiv"] = safe_float(cosfic)

        attrs["Rezultat"] = sm_data.get("Result", "")
        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_smart_meter_data(self) -> dict | None:
        if not self.coordinator.data:
            return None
        return (
            self.coordinator.data.get("smart_meter", {}).get(
                self._ctx.pod_name
            )
        )


# ── Helpers valoare instantanee ─────────────────────


def _parse_comma_float(value: str | None) -> float | None:
    """Parsează un număr cu virgulă ca separator zecimal (format european)."""
    if not value or value == "-9999":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _get_instant_data(coordinator, pod_name: str) -> dict | None:
    """Returnează dict-ul instant_values pentru un POD dat."""
    if not coordinator.data:
        return None
    return coordinator.data.get("instant_values", {}).get(pod_name)


def _get_instant_energy(instant_data: dict, code: str) -> float | None:
    """Extrage o valoare din energyReadingList pe baza codului (EA, EAP, ER, ERC)."""
    if not instant_data:
        return None
    value_list = instant_data.get("dataIstantValueList")
    if not value_list or not isinstance(value_list, list) or len(value_list) == 0:
        return None
    first = value_list[0]
    readings = first.get("energyReadingList")
    if not readings or not isinstance(readings, list):
        return None
    for r in readings:
        if r.get("ENERGY_TYPE") == code:
            return _parse_comma_float(r.get("VALUE"))
    return None


# ── Valoare instantanee Consum ──────────────────────


class ValoareInstantaneeConsumSensor(ReteleElectriceSensorBase):
    """Senzor pentru valoarea instantanee a energiei consumate (EA)."""

    _attr_has_entity_name = True
    _attr_translation_key = "valoare_instantanee_consum"
    _attr_icon = "mdi:flash"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"

    def __init__(
        self,
        coordinator: ReteleElectriceCoordinator,
        config_entry: ConfigEntry,
        ctx: PodContext,
    ) -> None:
        super().__init__(
            coordinator, config_entry, ctx,
            sensor_key="valoare_instantanee_consum",
            sensor_name="Valoare instantanee consum",
            icon="mdi:flash",
        )
        self._attr_unique_id = f"{DOMAIN}_{ctx.pod_name}_valoare_instantanee_consum"

    @property
    def native_value(self) -> float | None:
        """Valoarea principală: Energie activă consumată (EA) în kWh."""
        if not _is_license_valid(self.hass):
            return None
        instant = _get_instant_data(self.coordinator, self._ctx.pod_name)
        return _get_instant_energy(instant, "EA")

    @property
    def extra_state_attributes(self) -> dict:
        """Atribute secundare: tensiuni, curenți, putere, energie reactivă."""
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}
        attrs: dict = {}
        instant = _get_instant_data(self.coordinator, self._ctx.pod_name)
        if not instant:
            attrs["attribution"] = ATTRIBUTION
            return attrs

        value_list = instant.get("dataIstantValueList")
        if not value_list or not isinstance(value_list, list) or len(value_list) == 0:
            attrs["attribution"] = ATTRIBUTION
            return attrs

        first = value_list[0]

        # Tensiuni per fază
        for phase, key in [("R", "UR_VALUE"), ("S", "US_VALUE"), ("T", "UT_VALUE")]:
            val = _parse_comma_float(first.get(key))
            if val is not None:
                attrs[f"Tensiune faza {phase} (V)"] = val

        # Curenți per fază
        for phase, key in [("R", "IR_VALUE"), ("S", "IS_VALUE"), ("T", "IT_VALUE")]:
            val = _parse_comma_float(first.get(key))
            if val is not None:
                attrs[f"Curent faza {phase} (A)"] = val

        # Putere activă instantanee
        p_val = _parse_comma_float(first.get("P_VALUE"))
        if p_val is not None:
            attrs["Putere activă instantanee (kW)"] = p_val

        # Energie reactivă (ER) — doar pe senzorul de consum
        er_val = _get_instant_energy(instant, "ER")
        if er_val is not None:
            attrs["Energie reactivă (kVArh)"] = er_val

        # Metadate
        reading_date = first.get("READING_DATE", "")
        if reading_date:
            attrs["Data citire"] = reading_date
        last_updated = first.get("LAST_UPDATED", "")
        if last_updated:
            attrs["Ultima actualizare"] = last_updated
        meter = first.get("METER", "")
        if meter:
            attrs["Contor"] = meter

        result = instant.get("Result", "")
        if result:
            attrs["Rezultat"] = result

        attrs["attribution"] = ATTRIBUTION
        return attrs


# ── Valoare instantanee Producție ───────────────────


class ValoareInstantaneeProductieSensor(ReteleElectriceSensorBase):
    """Senzor pentru valoarea instantanee a energiei produse (EAP) — doar prosumer."""

    _attr_has_entity_name = True
    _attr_translation_key = "valoare_instantanee_productie"
    _attr_icon = "mdi:solar-power"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"

    def __init__(
        self,
        coordinator: ReteleElectriceCoordinator,
        config_entry: ConfigEntry,
        ctx: PodContext,
    ) -> None:
        super().__init__(
            coordinator, config_entry, ctx,
            sensor_key="valoare_instantanee_productie",
            sensor_name="Valoare instantanee producție",
            icon="mdi:solar-power",
        )
        self._attr_unique_id = f"{DOMAIN}_{ctx.pod_name}_valoare_instantanee_productie"

    @property
    def native_value(self) -> float | None:
        """Valoarea principală: Energie activă produsă (EAP) în kWh."""
        if not _is_license_valid(self.hass):
            return None
        instant = _get_instant_data(self.coordinator, self._ctx.pod_name)
        return _get_instant_energy(instant, "EAP")

    @property
    def extra_state_attributes(self) -> dict:
        """Atribute secundare: EAP, ERC."""
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}
        attrs: dict = {}
        instant = _get_instant_data(self.coordinator, self._ctx.pod_name)
        if not instant:
            attrs["attribution"] = ATTRIBUTION
            return attrs

        # Energie activă produsă (EAP) — duplicat în atribute pentru vizibilitate
        eap_val = _get_instant_energy(instant, "EAP")
        if eap_val is not None:
            attrs["Energie activă produsă (kWh)"] = eap_val

        # Energie reactivă capacitivă (ERC) — doar pe senzorul de producție
        erc_val = _get_instant_energy(instant, "ERC")
        if erc_val is not None:
            attrs["Energie reactivă capacitivă (kVArh)"] = erc_val

        value_list = instant.get("dataIstantValueList")
        if value_list and isinstance(value_list, list) and len(value_list) > 0:
            first = value_list[0]
            reading_date = first.get("READING_DATE", "")
            if reading_date:
                attrs["Data citire"] = reading_date
            last_updated = first.get("LAST_UPDATED", "")
            if last_updated:
                attrs["Ultima actualizare"] = last_updated
            meter = first.get("METER", "")
            if meter:
                attrs["Contor"] = meter

        result_val = instant.get("Result", "")
        if result_val:
            attrs["Rezultat"] = result_val

        attrs["attribution"] = ATTRIBUTION
        return attrs


# ── Helpers date furnizor ────────────────────────────

_LUNI_RO = {
    1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
    5: "mai", 6: "iunie", 7: "iulie", 8: "august",
    9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie",
}


def _format_date_friendly(date_str: str | None) -> str | None:
    """Convertește o dată ISO (2025-11-11) sau dd.mm.yyyy în format prietenos.

    Exemplu: '2025-11-11' → '11 noiembrie 2025'
             '2024-05-17' → '17 mai 2024'
    """
    if not date_str:
        return None
    date_str = date_str.strip()
    # Format ISO: yyyy-mm-dd
    if len(date_str) >= 10 and date_str[4] == "-":
        try:
            parts = date_str[:10].split("-")
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            luna = _LUNI_RO.get(m, str(m))
            return f"{d} {luna} {y}"
        except (ValueError, IndexError):
            pass
    # Format dd.mm.yyyy
    if len(date_str) >= 10 and date_str[2] == ".":
        try:
            parts = date_str[:10].split(".")
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            luna = _LUNI_RO.get(m, str(m))
            return f"{d} {luna} {y}"
        except (ValueError, IndexError):
            pass
    return date_str


# ── Date furnizor ───────────────────────────────────


class DateFurnizorSensor(ReteleElectriceSensorBase):
    """Senzor pentru datele furnizorului de energie asociat POD-ului."""

    _attr_has_entity_name = True
    _attr_translation_key = "date_furnizor"
    _attr_icon = "mdi:office-building"

    def __init__(
        self,
        coordinator: ReteleElectriceCoordinator,
        config_entry: ConfigEntry,
        ctx: PodContext,
    ) -> None:
        super().__init__(
            coordinator, config_entry, ctx,
            sensor_key="date_furnizor",
            sensor_name="Date furnizor",
            icon="mdi:office-building",
        )
        self._attr_unique_id = f"{DOMAIN}_{ctx.pod_name}_date_furnizor"

    @property
    def native_value(self) -> str | None:
        """Valoarea principală: CUI furnizor."""
        if not _is_license_valid(self.hass):
            return "Licență necesară"
        supplier = self._get_supplier_data()
        if not supplier:
            return None
        return supplier.get("cui")

    @property
    def extra_state_attributes(self) -> dict:
        """Atribute secundare: toate datele furnizorului și POD-ului."""
        if not _is_license_valid(self.hass):
            return {"attribution": ATTRIBUTION}
        attrs: dict = {}
        supplier = self._get_supplier_data()
        if not supplier:
            attrs["attribution"] = ATTRIBUTION
            return attrs

        # ── Date furnizor ──
        furnizor = supplier.get("furnizor")
        if furnizor:
            attrs["Furnizor"] = furnizor

        furnizor_pre = supplier.get("furnizor_pre")
        if furnizor_pre:
            attrs["PRE (Operator distribuție)"] = furnizor_pre

        cui = supplier.get("cui")
        if cui:
            attrs["CUI furnizor"] = cui

        # ── Date client ──
        nume = supplier.get("nume_client")
        if nume:
            attrs["Nume client"] = nume

        adresa_client = supplier.get("adresa_client")
        if adresa_client:
            attrs["Adresă client"] = adresa_client

        adresa_locons = supplier.get("adresa_locons")
        if adresa_locons:
            attrs["Adresă loc de consum"] = adresa_locons

        # ── Date tehnice POD ──
        kw_aprobata = supplier.get("kw_aprobata")
        if kw_aprobata:
            attrs["Putere aprobată (kW)"] = kw_aprobata

        kw_evacuata = supplier.get("kw_evacuata")
        if kw_evacuata:
            attrs["Putere evacuată (kW)"] = kw_evacuata

        delimitare = supplier.get("delimitare")
        if delimitare:
            attrs["Punct delimitare"] = delimitare

        u_delimitare = supplier.get("u_delimitare")
        if u_delimitare:
            attrs["Tensiune punct delimitare"] = u_delimitare

        racordare = supplier.get("racordare")
        if racordare and racordare.strip() not in ("", "-"):
            attrs["Punct de racordare"] = racordare

        # ── Stare ──
        activ = supplier.get("activ")
        if activ:
            attrs["Stare"] = "Activ" if activ == "D" else "Inactiv"

        deconectat = supplier.get("deconectat")
        if deconectat:
            attrs["Deconectat"] = "Da" if deconectat == "D" else "Nu"

        activ_furnizor = supplier.get("activ_furnizor_la")
        if activ_furnizor:
            attrs["Activ furnizor de la"] = _format_date_friendly(activ_furnizor)

        activ_consumator = supplier.get("activ_consumator_la")
        if activ_consumator:
            attrs["Activ consumator de la"] = _format_date_friendly(activ_consumator)

        # ── ATR / CER ──
        atr_number = supplier.get("atr_number")
        atr_date = supplier.get("atr_date")
        if atr_number:
            atr_str = atr_number
            if atr_date:
                atr_str += f" / {_format_date_friendly(atr_date)}"
            attrs["Nr. și data ATR/CER"] = atr_str

        cer_version = supplier.get("cer_version")
        cer_date = supplier.get("cer_date")
        if cer_version:
            cer_str = f"v{cer_version}"
            if cer_date:
                cer_str += f" / {_format_date_friendly(cer_date)}"
            attrs["Versiune CER"] = cer_str

        # ── Telecitire ──
        telecitit = supplier.get("telecitit")
        if telecitit:
            attrs["Telecitire"] = "Da" if telecitit == "D" else "Nu"

        # ── Contor ──
        contoare = supplier.get("Contor")
        if contoare and isinstance(contoare, list) and len(contoare) > 0:
            c = contoare[0]
            seria = c.get("seria")
            if seria:
                attrs["Seria contorului"] = seria
            marca = c.get("marca")
            if marca:
                attrs["Marca contor"] = marca
            det_tip = c.get("det_tip")
            if det_tip:
                attrs["Tip contor"] = det_tip
            data_montare = c.get("data_montare")
            if data_montare:
                attrs["Data montare"] = _format_date_friendly(data_montare)
            precizie = c.get("precizie")
            if precizie:
                attrs["Precizie"] = precizie
            constanta = c.get("constanta")
            if constanta:
                attrs["Constantă"] = constanta

        # ── Zonă distribuție ──
        cft_desc = supplier.get("cft_description")
        if cft_desc:
            attrs["Zonă distribuție"] = cft_desc

        cft_ou = supplier.get("cft_ou_description")
        if cft_ou:
            attrs["Unitate operațională"] = cft_ou

        cft_district = supplier.get("cft_district_uo")
        if cft_district:
            attrs["Județ distribuție"] = cft_district

        # ── Altele ──
        aggregation = supplier.get("aggregation_formula")
        if aggregation:
            attrs["Formula agregare"] = aggregation

        compensation = supplier.get("compensation_mode")
        if compensation:
            attrs["Mod compensare"] = compensation

        corectii = supplier.get("corectii")
        if corectii and corectii.strip() not in ("", "-"):
            attrs["Corecții"] = corectii

        attrs["attribution"] = ATTRIBUTION
        return attrs

    def _get_supplier_data(self) -> dict | None:
        """Returnează dict-ul supplier_data pentru POD-ul curent."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("supplier_data", {}).get(
            self._ctx.pod_name
        )
