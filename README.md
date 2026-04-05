# Rețele Electrice — Integrare Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.x%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/cnecrea/reteleelectrice)](https://github.com/cnecrea/reteleelectrice/releases)
[![GitHub Stars](https://img.shields.io/github/stars/cnecrea/reteleelectrice?style=flat&logo=github)](https://github.com/cnecrea/reteleelectrice/stargazers)
[![Instalări](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/reteleelectrice/main/statistici/shields/descarcari.json)](https://github.com/cnecrea/reteleelectrice)
[![Ultima versiune](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/reteleelectrice/main/statistici/shields/ultima_release.json)](https://github.com/cnecrea/reteleelectrice/releases/latest)

Integrare custom pentru [Home Assistant](https://www.home-assistant.io/) care monitorizează contul [Rețele Electrice](https://contulmeu.reteleelectrice.ro/) — puncte de consum (POD), indexuri contor, arhivă citiri, întreruperi de curent și date smart meter, toate prin portalul Salesforce Experience Cloud al Rețele Electrice.

Oferă senzori dedicați per POD: informații contract, date utilizator, index citire consum/producție (compatibil Energy dashboard), arhivă energie consumată/produsă pe an, întreruperi curent și smart meter consum/producție. Formatare completă în limba română cu diacritice, date calendaristice și valori în kWh.

---

## Ce face integrarea

- **Informații POD** — tip contract, putere absorbită/cedată, serie contor, adresă, tarif, profil consum
- **Date utilizator** — nume, email, telefon, CNP, adresă, județ, tip cont
- **Index citire consum** — ultimul index contor pentru energie consumată (kWh), cu consum lunar calculat
- **Index citire producție** — ultimul index contor pentru energie produsă (kWh, doar prosumer)
- **Arhivă energie consumată** — citiri consum grupate pe an, cu total anual calculat (maxim 2 ani)
- **Arhivă energie produsă** — citiri producție grupate pe an (doar prosumer, maxim 2 ani)
- **Întreruperi curent** — status curent pentru fiecare POD (întrerupere activă / fără întreruperi)
- **Smart Meter Consum** — total energie consumată din smart meter (kWh, compatibil Energy dashboard)
- **Smart Meter Producție** — total energie produsă din smart meter (kWh, doar prosumer)
- **Licențiere** — sistem de licențe cu perioadă de evaluare și activare online
- **Sistem de licență** — fără licență validă se afișează doar „Licență necesară" pe toți senzorii
- **Reconfigurare fără reinstalare** — OptionsFlow pentru modificarea credențialelor, POD-urilor și licenței

---

## Sursa datelor

Datele vin prin portalul Salesforce Experience Cloud al Rețele Electrice (`contulmeu.reteleelectrice.ro`), care expune:

| Metodă | Descriere |
|--------|-----------|
| Aura — `getUserName` | Nume utilizator autentificat |
| Aura — `getAccountInfo` | Informații cont (nume, CNP, email, adresă) |
| Aura — `getContactInfo` | Informații contact (email, telefon) |
| Aura — `getPODs` | Lista punctelor de consum (POD) |
| Aura — `getPodDetails` | Detalii per POD (contract, putere, contor, tip) |
| VF Proxy — `ReadingArchive` | Arhivă citiri contor (indexuri lunare EA/EAP) |
| VF Proxy — `PowerOutages` | Status întreruperi curent per POD |
| VF Proxy — `SmartMeterData` | Date smart meter (SUM_EA, SUM_EAP, MAX, COSFI) |

Autentificarea se face cu email + parolă prin login Salesforce Experience Cloud (VF page + A4J callout). Sesiunea este menținută prin aiohttp CookieJar.

---

## Instalare

### HACS (recomandat)

1. Deschide HACS în Home Assistant
2. Click pe cele 3 puncte (⋮) din colțul dreapta sus → **Custom repositories**
3. Adaugă URL-ul: `https://github.com/cnecrea/reteleelectrice`
4. Categorie: **Integration**
5. Click **Add** → găsește „Rețele Electrice" → **Install**
6. Restartează Home Assistant

### Manual

1. Copiază folderul `custom_components/reteleelectrice/` în directorul `config/custom_components/` din Home Assistant
2. Restartează Home Assistant

---

## Configurare

### Pasul 1 — Adaugă integrarea

1. **Setări** → **Dispozitive și Servicii** → **Adaugă Integrare**
2. Caută „**Rețele Electrice**"
3. Completează formularul:

| Câmp | Descriere | Implicit |
|------|-----------|----------|
| **Email** | Adresa de email a contului contulmeu.reteleelectrice.ro | — |
| **Parolă** | Parola contului | — |
| **Interval actualizare** | Secunde între interogările API | `3600` (1 oră) |

### Pasul 2 — Selectare POD-uri

După autentificare, se afișează lista punctelor de consum descoperite:

- **Monitorizează toate punctele de consum** — activează pentru a urmări toate POD-urile
- **Selectare individuală** — alege doar POD-urile dorite

### Pasul 3 — Licență

Integrarea necesită o licență validă. Poți achiziționa una de la [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice). Licența se introduce din **OptionsFlow** (Setări → Dispozitive și Servicii → Rețele Electrice → Configurare → Licență).

### Pasul 4 — Reconfigurare (opțional)

Setările pot fi modificate după instalare, fără a șterge integrarea:

1. **Setări** → **Dispozitive și Servicii** → click pe **Rețele Electrice**
2. Click pe **Configurare** (⚙️)
3. Alege **Setări cont**, **Selectare POD-uri** sau **Licență**
4. Modifică setările dorite → **Salvează** (integrarea se reîncarcă automat, fără restart)

Detalii complete în [SETUP.md](SETUP.md).

---

## Entități create

Integrarea creează un **device** per POD: „Rețele Electrice {POD}" cu următorii senzori:

### Senzori per POD

| Senzor | Entity ID | Valoare principală | Energy dashboard |
|--------|-----------|-------------------|------------------|
| POD | `sensor.reteleelectrice_{pod}_informatii_pod` | Tip contract (ex: Prosumer) | — |
| Date utilizator | `sensor.reteleelectrice_{pod}_informatii_cont` | Numele complet | — |
| Index citire consum | `sensor.reteleelectrice_{pod}_index_citire_consum` | Index contor (kWh) | TOTAL_INCREASING |
| Index citire producție | `sensor.reteleelectrice_{pod}_index_citire_productie` | Index contor (kWh) | TOTAL_INCREASING |
| {an} → Energie consumată | `sensor.reteleelectrice_{pod}_arhiva_energie_consumata_{an}` | Total anual (ex: „1896.0 kWh") | — |
| {an} → Energie produsă | `sensor.reteleelectrice_{pod}_arhiva_energie_produsa_{an}` | Total anual (ex: „569.0 kWh") | — |
| Întreruperi curent | `sensor.reteleelectrice_{pod}_intreruperi_curent` | Status întrerupere | — |
| Smart Meter Consum | `sensor.reteleelectrice_{pod}_smart_meter_consum` | Total consum (kWh) | TOTAL |
| Smart Meter Producție | `sensor.reteleelectrice_{pod}_smart_meter_productie` | Total producție (kWh) | TOTAL |

> **Notă**: Senzorii „Index citire producție", „{an} → Energie produsă" și „Smart Meter Producție" apar doar pentru POD-uri de tip **prosumer**. „Smart Meter Consum" și „Smart Meter Producție" apar doar pentru POD-uri cu **smart meter**.

---

### Senzor: POD

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_informatii_pod`
**Valoare principală**: tipul contractului (ex: „Prosumer", „Consumator casnic")
**Icon**: `mdi:file-document-outline`

**Atribute**:
```yaml
POD: "RO001EXXXXXXXXX"
Adresă: "Str. Exemplu Nr. 10, Localitatea, Județul"
Tip contract: "Prosumer"
Stare contract: "Activ"
Tip consumator: "Casnic"
Piață: "Reglementată"
Putere absorbită (kW): 5.75
Putere absorbită (kVA): 6.0
Putere cedată (kW): 3.0
Putere cedată (kVA): 3.5
Nivel tensiune: "JT"
Tensiune nominală (kV): 0.4
Serie contor: "12345678"
Tip contor: "Electronic Trifazat"
Smart meter: true
Prosumer: true
Tarif: "A2.1"
Profil consum: "Casnic"
Constantă contor: 1
Precizie: 1
Unitate operativă: "UO Exemplu"
Zonă: "Z01"
Cod CFT: "CFT001"
ATR: "ATR001"
Perioadă măsurare: "Lunar"
Dată start contract: "2020-01-15"
Distribuitor: "E-Distribuție"
```

---

### Senzor: Date utilizator

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_informatii_cont`
**Valoare principală**: numele complet (ex: „Popescu Ion")
**Icon**: `mdi:account-circle`

**Atribute**:
```yaml
Nume: "Popescu Ion"
Email: "exemplu@email.ro"
Telefon: "+40712345678"
CNP: "1XXXXXXXXXXXX"
Cod fiscal: ""
Adresă: "Str. Exemplu Nr. 10"
Oraș: "București"
Județ: "București"
Cod poștal: "010101"
Tip cont: "Persoana Fizică"
```

---

### Senzor: Index citire consum

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_consum`
**Valoare principală**: `45000.0` (kWh — valoare numerică float)
**Device class**: `energy` | **State class**: `total_increasing` | **Unitate**: `kWh`
**Icon**: `mdi:counter`

**Atribute**:
```yaml
Data citire: "1 martie 2026"
Tip citire: "Index"
Serie contor: "12345678"
Constantă: 1
Index energie consumată (kWh): 45000.0
Consum lunar (kWh): 350.5
Citire anterioară: "1 februarie 2026"
```

---

### Senzor: Index citire producție

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_productie`
**Valoare principală**: `12000.0` (kWh — valoare numerică float)
**Device class**: `energy` | **State class**: `total_increasing` | **Unitate**: `kWh`
**Icon**: `mdi:solar-power`

> Doar pentru POD-uri de tip **prosumer**.

**Atribute**:
```yaml
Data citire: "1 martie 2026"
Tip citire: "Index"
Serie contor: "12345678"
Constantă: 1
Index energie produsă (kWh): 12000.0
Producție lunară (kWh): 280.2
Citire anterioară: "1 februarie 2026"
```

---

### Senzor: {an} → Energie consumată

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_arhiva_energie_consumata_2026`
**Valoare principală**: `„1896.0 kWh"` (text cu total anual calculat)
**Icon**: `mdi:history`

Se creează câte un senzor per an (maxim 2 ani), cu numele: `2026 → Energie consumată`, `2025 → Energie consumată`.

**Atribute** (câte o intrare per citire lunară):
```yaml
1 martie 2026: "45000.0 kWh"
1 februarie 2026: "44650.0 kWh"
1 ianuarie 2026: "44280.0 kWh"
Total citiri: 3
Serie contor: "12345678"
```

---

### Senzor: {an} → Energie produsă

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_arhiva_energie_produsa_2026`
**Valoare principală**: `„569.0 kWh"` (text cu total anual calculat)
**Icon**: `mdi:solar-power`

> Doar pentru POD-uri de tip **prosumer**. Structură identică cu „Energie consumată", dar pentru EAP.

**Atribute**:
```yaml
1 martie 2026: "12000.0 kWh"
1 februarie 2026: "11720.0 kWh"
1 ianuarie 2026: "11431.0 kWh"
Total citiri: 3
Serie contor: "12345678"
```

---

### Senzor: Întreruperi curent

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_intreruperi_curent`
**Valoare principală**: „Fără întreruperi" sau „Întrerupere activă"
**Icon**: `mdi:flash-alert`

**Atribute**:
```yaml
POD: "RO001EXXXXXXXXX"
Mesaj: "Nu există întreruperi programate sau în desfășurare."
Verificare întreruperi: "true"
Rezultat: "OK"
```

---

### Senzor: Smart Meter Consum

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_smart_meter_consum`
**Valoare principală**: `1822.419` (kWh — valoare numerică float)
**Device class**: `energy` | **State class**: `total` | **Unitate**: `kWh`
**Icon**: `mdi:chart-line`

> Doar pentru POD-uri cu **smart meter**.

**Atribute**:
```yaml
POD: "RO001EXXXXXXXXX"
Contor: "12345678"
Perioadă start: "01.01.2026"
Perioadă sfârșit: "31.03.2026"
Total energie consumată (kWh): 1822.419
Vârf consum (kWh): 4.5
Total energie reactivă (kVArh): 150.3
Vârf energie reactivă (kVArh): 1.2
Factor de putere (cosφ): 0.95
Rezultat: "OK"
```

---

### Senzor: Smart Meter Producție

**Entity ID**: `sensor.reteleelectrice_RO001EXXXXXXXXX_smart_meter_productie`
**Valoare principală**: `563.03` (kWh — valoare numerică float)
**Device class**: `energy` | **State class**: `total` | **Unitate**: `kWh`
**Icon**: `mdi:solar-power`

> Doar pentru POD-uri de tip **prosumer** cu **smart meter**.

**Atribute**:
```yaml
POD: "RO001EXXXXXXXXX"
Contor: "12345678"
Perioadă start: "01.01.2026"
Perioadă sfârșit: "31.03.2026"
Total energie produsă (kWh): 563.03
Vârf producție (kWh): 3.8
Total energie reactivă capacitivă (kVArh): 45.2
Vârf energie reactivă capacitivă (kVArh): 0.8
Factor de putere capacitiv: 0.97
Rezultat: "OK"
```

---

### Senzor: Licență (fără licență validă)

Când licența nu este activă, toți senzorii afișează „Licență necesară" ca valoare principală, iar atributele sunt reduse la `{"attribution": "..."}`.

---

## Exemple de automatizări

### Notificare întrerupere curent

```yaml
automation:
  - alias: "Notificare întrerupere curent"
    trigger:
      - platform: state
        entity_id: sensor.reteleelectrice_RO001EXXXXXXXXX_intreruperi_curent
        to: "Întrerupere activă"
    action:
      - service: notify.mobile_app_telefonul_meu
        data:
          title: "Întrerupere de curent!"
          message: >
            POD-ul {{ state_attr('sensor.reteleelectrice_RO001EXXXXXXXXX_intreruperi_curent', 'POD') }}
            are o întrerupere activă.
```

### Notificare consum lunar ridicat

```yaml
automation:
  - alias: "Notificare consum lunar ridicat"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_consum', 'Consum lunar (kWh)') | float > 500 }}
    action:
      - service: notify.mobile_app_telefonul_meu
        data:
          title: "Consum lunar ridicat"
          message: >
            Consumul lunar a depășit 500 kWh:
            {{ state_attr('sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_consum', 'Consum lunar (kWh)') }} kWh.
```

### Card pentru Dashboard

```yaml
type: entities
title: Rețele Electrice
entities:
  - entity: sensor.reteleelectrice_RO001EXXXXXXXXX_informatii_pod
    name: POD
  - entity: sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_consum
    name: Index consum
  - entity: sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_productie
    name: Index producție
  - entity: sensor.reteleelectrice_RO001EXXXXXXXXX_smart_meter_consum
    name: Smart Meter Consum
  - entity: sensor.reteleelectrice_RO001EXXXXXXXXX_intreruperi_curent
    name: Întreruperi
```

### Adăugare în Energy Dashboard

Senzorii compatibili cu Energy dashboard:

- **Consum**: `sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_consum` (TOTAL_INCREASING) sau `sensor.reteleelectrice_RO001EXXXXXXXXX_smart_meter_consum` (TOTAL)
- **Producție**: `sensor.reteleelectrice_RO001EXXXXXXXXX_index_citire_productie` (TOTAL_INCREASING) sau `sensor.reteleelectrice_RO001EXXXXXXXXX_smart_meter_productie` (TOTAL)

Navighează la **Setări** → **Dashboards** → **Energie** și adaugă senzorii în secțiunile corespunzătoare.

---

## Structura fișierelor

```
custom_components/reteleelectrice/
├── __init__.py          # Setup/unload integrare (runtime_data pattern, LicenseManager)
├── api.py               # Client API async — login Salesforce, Aura + VF proxy
├── config_flow.py       # ConfigFlow + OptionsFlow (autentificare, POD-uri, licență)
├── const.py             # Constante, URL-uri, chei date coordinator
├── coordinator.py       # DataUpdateCoordinator — fetch per-POD (citiri, outages, smart meter)
├── diagnostics.py       # Export diagnostic (licență, coordinator, senzori activi)
├── helpers.py           # Funcții utilitare (format date, normalize, safe_float, județe)
├── license.py           # Manager licență (server-side v3.3, Ed25519, HMAC-SHA256)
├── manifest.json        # Metadata integrare
├── sensor.py            # Clase senzor (9 tipuri per POD)
├── strings.json         # Traduceri implicite (română)
├── translations/
│   ├── en.json          # Traduceri engleză
│   └── ro.json          # Traduceri română
└── brand/
    ├── icon.png         # Pictogramă integrare
    ├── icon@2x.png      # Pictogramă retina
    ├── logo.png         # Logo integrare
    ├── logo@2x.png      # Logo retina
    ├── dark_icon.png    # Pictogramă dark mode
    ├── dark_icon@2x.png # Pictogramă dark mode retina
    ├── dark_logo.png    # Logo dark mode
    └── dark_logo@2x.png # Logo dark mode retina
```

---

## Cerințe

- **Home Assistant** 2024.x sau mai nou (pattern `entry.runtime_data`)
- **HACS** (opțional, pentru instalare ușoară)
- **Cont Rețele Electrice** activ — contulmeu.reteleelectrice.ro (email + parolă)
- **Licență** validă — [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)
- **Dependențe Python**: `cryptography>=41.0.0`, `beautifulsoup4>=4.12.0` (instalate automat de Home Assistant)

---

## Limitări cunoscute

1. **O singură instanță per cont** — dacă încerci să adaugi același email de două ori, vei primi eroare „Acest cont Rețele Electrice este deja configurat".

2. **Arhivă citiri — maxim 2 ani** — se creează senzori doar pentru ultimii 2 ani disponibili în portalul Rețele Electrice.

3. **Smart Meter — doar pentru POD-uri cu contor inteligent** — senzorii Smart Meter Consum și Smart Meter Producție apar doar dacă POD-ul are flag-ul smart meter activ.

4. **Producție — doar prosumer** — senzorii de producție (Index citire producție, Energie produsă, Smart Meter Producție) sunt creați doar pentru POD-uri cu contract de tip prosumer.

5. **Interval minim de actualizare** — minimum 1 oră (3600 secunde), maximum 24 ore (86400 secunde), pentru a nu suprasolicita portalul Rețele Electrice.

6. **Sesiune Salesforce** — portalul contulmeu.reteleelectrice.ro folosește Salesforce Experience Cloud. Sesiunea este menținută prin CookieJar; dacă serverul Salesforce resetează sesiunea, integrarea face re-login automat la următorul ciclu.

---

## Susține dezvoltatorul

Dacă ți-a plăcut această integrare și vrei să sprijini munca depusă, **invită-mă la o cafea**!
Contribuția ta ajută la dezvoltarea viitoare a proiectului.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Susține%20dezvoltatorul-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/cnecrea)

---

## Contribuții

Contribuțiile sunt binevenite! Simte-te liber să trimiți un pull request sau să raportezi probleme [aici](https://github.com/cnecrea/reteleelectrice/issues).

---

## Suport

Dacă îți place această integrare, oferă-i un ⭐ pe [GitHub](https://github.com/cnecrea/reteleelectrice/)!

## Licență

MIT
