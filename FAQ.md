# FAQ — Întrebări frecvente

Răspunsuri la cele mai comune întrebări despre integrarea **Rețele Electrice** pentru Home Assistant.

---

### Ce credențiale folosesc?

Folosește email-ul și parola contului de pe portalul contulmeu.reteleelectrice.ro — aceleași cu care te autentifici pe site-ul Rețele Electrice. Nu sunt necesare API key-uri sau token-uri suplimentare.

---

### Ce date extrage integrarea din contul meu?

Integrarea aduce per POD (punct de consum): informații contract (tip, putere, tarif, contor), date utilizator (nume, email, telefon, CNP), ultimul index contor pentru consum și producție, arhivă citiri pe ultimii 2 ani, status întreruperi de curent și date smart meter (total consum/producție, vârf, factor de putere).

Nu se fac modificări pe cont, nu se trimit cereri și nu se modifică setări — integrarea este **read-only**.

---

### Ce este un POD?

POD (Punct de Livrare / Point of Delivery) este codul unic care identifică un punct de consum în rețeaua electrică. Format: `RO001EXXXXXXXXX`. Fiecare POD corespunde unui loc de consum (apartament, casă, etc.) și este vizibil pe factura de energie sau pe portalul contulmeu.reteleelectrice.ro.

---

### Cât de des se actualizează datele?

Implicit, la fiecare oră (3600 secunde). Intervalul minim este 1 oră, maximul 24 ore. Poți modifica intervalul prin reconfigurarea integrării (OptionsFlow → Setări cont). La fiecare ciclu, toate datele per POD sunt aduse într-un singur ciclu al coordinator-ului.

---

### Pot adăuga mai multe conturi Rețele Electrice?

Da, fiecare cont (email diferit) se adaugă ca intrare separată. Nu poți adăuga același email de două ori — integrarea detectează duplicatele și refuză cu mesajul „Acest cont Rețele Electrice este deja configurat".

---

### Pot alege ce POD-uri să monitorizez?

Da. La configurare și din OptionsFlow, poți alege între „Monitorizează toate punctele de consum" sau selectare individuală. Poți modifica selecția oricând fără a șterge integrarea.

---

### De ce nu văd senzori de producție (EAP)?

Senzorii „Index citire producție", „Energie produsă" și „Smart Meter Producție" sunt creați **doar** pentru POD-uri cu contract de tip **prosumer**. Dacă POD-ul tău nu este prosumer, acești senzori nu vor apărea. Verifică tipul contractului pe portalul contulmeu.reteleelectrice.ro.

---

### De ce nu văd senzorii Smart Meter?

Senzorii „Smart Meter Consum" și „Smart Meter Producție" sunt creați **doar** pentru POD-uri care au contor inteligent (smart meter). Dacă POD-ul tău nu are smart meter, acești senzori nu vor apărea.

---

### Pot adăuga senzorii în Energy Dashboard?

Da. Senzorii compatibili cu Energy Dashboard sunt:

| Senzor | State class | Utilizare |
|--------|------------|-----------|
| Index citire consum | `total_increasing` | Consum rețea (Grid consumption) |
| Index citire producție | `total_increasing` | Producție solară (Solar production) |
| Smart Meter Consum | `total` | Consum rețea (alternativă la index) |
| Smart Meter Producție | `total` | Producție solară (alternativă la index) |

Navighează la **Setări** → **Dashboards** → **Energie** și adaugă senzorii în secțiunile corespunzătoare.

---

### Ce e licența și de ce am nevoie de ea?

Integrarea folosește un sistem de licențiere server-side (v3.3) cu semnături Ed25519 și HMAC-SHA256. Fără o licență validă, toți senzorii afișează „Licență necesară" și nu expun date reale.

Licența se achiziționează de la: [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)

După achiziție, introdu cheia de licență din OptionsFlow:
1. **Setări** → **Dispozitive și Servicii** → **Rețele Electrice** → **Configurare**
2. Selectează **Licență**
3. Completează câmpul „Cheie de licență" (format: `RETE-XXXX-XXXX-XXXX-XXXX`)
4. Salvează

---

### De ce apare „Licență necesară" pe toți senzorii?

Integrarea folosește un sistem de licențiere. Dacă perioada de evaluare a expirat sau licența nu a fost activată, toți senzorii afișează „Licență necesară". Datele continuă să fie aduse de la portal, dar nu sunt expuse. Activează o licență din OptionsFlow → Licență (vezi [SETUP.md](SETUP.md)).

---

### Am introdus licența dar senzorii tot arată „Licență necesară". De ce?

Câteva cauze posibile:

1. **Licența nu a fost validată** — verifică log-urile pentru mesaje cu `LICENSE` sau `ReteleElectrice:License`
2. **Serverul de licențe nu este accesibil** — dacă HA nu are acces la internet, validarea eșuează
3. **Cheie greșită** — verifică că ai copiat cheia corect, fără spații suplimentare (format: `RETE-XXXX-XXXX-XXXX-XXXX`)
4. **Restartare necesară** — în rare cazuri, un restart al HA poate rezolva problema

Activează debug logging ([DEBUG.md](DEBUG.md)) și caută mesaje legate de licență.

---

### Unde obțin o cheie de licență?

Link-ul de achiziție este afișat direct în interfața integrării (OptionsFlow → Licență) și este: [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice). Sunt disponibile licențe lunare, anuale și perpetue.

---

### Ce tipuri de licență există?

| Tip | Descriere |
|-----|-----------|
| **Trial** | Perioadă de evaluare — se activează automat la prima instalare |
| **Lunară** | Licență valabilă 30 de zile de la activare |
| **Anuală** | Licență valabilă 365 de zile de la activare |
| **Perpetuă** | Licență fără expirare |

---

### Licența este legată de dispozitiv?

Da. Cheia de licență este legată de instalarea Home Assistant prin fingerprint (SHA-256 din UUID + machine-id). Dacă muți instalarea pe alt hardware, va trebui să contactezi suportul pentru transfer sau să achiziționezi o licență nouă.

---

### Ce se întâmplă dacă serverul de licențe nu e accesibil?

Integrarea are un grace period (perioadă de grație): 72 de ore pentru licențe active și 24 de ore pentru trial. În acest interval, licența anterioară rămâne validă chiar dacă serverul nu este accesibil. După expirarea grace period-ului, senzorii vor afișa „Licență necesară".

---

### Ce înseamnă „Index citire consum" vs. „Smart Meter Consum"?

- **Index citire consum** — ultimul index al contorului, obținut din arhiva de citiri (citire lunară oficială). Valoare cumulativă (`total_increasing`), potrivit pentru Energy Dashboard.
- **Smart Meter Consum** — totalul energiei consumate pe o perioadă, obținut din datele smart meter. Valoare sumară pe perioadă (`total`), potrivit pentru Energy Dashboard.

Ambii senzori pot fi folosiți în Energy Dashboard, dar provin din surse diferite. Alege-l pe cel care ți se potrivește.

---

### Ce înseamnă datele din arhiva de citiri?

Arhiva de citiri conține indexurile contorului la fiecare citire lunară, pe ultimii 2 ani. Fiecare atribut arată data citirii (format „1 decembrie 2025") și valoarea indexului (kWh). Valoarea principală a senzorului este totalul consumat/produs pe an, calculat ca diferența între ultima și prima citire din an.

---

### De ce apar maxim 2 ani în arhiva de citiri?

Integrarea limitează senzorii de arhivă la ultimii 2 ani disponibili, pentru a nu supraîncărca Home Assistant cu entități inutile. Dacă portalul Rețele Electrice conține date pe mai mulți ani, doar ultimii 2 sunt expuși ca senzori.

---

### Cum creez o automatizare pentru întreruperi de curent?

```yaml
automation:
  - alias: "Alertă întrerupere curent"
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
            are o întrerupere de curent activă.
```

Înlocuiește `RO001EXXXXXXXXX` cu codul POD-ului tău.

---

### Integrarea trimite date personale către terți?

Integrarea comunică cu portalul Salesforce al Rețele Electrice (contulmeu.reteleelectrice.ro) pentru datele contului și cu un server de licențiere pentru validarea licenței. Către serverul de licențiere se trimite doar fingerprint-ul instalării și cheia de licență — nu se trimit parole, date personale sau informații despre consum.

---

### Ce biblioteci externe necesită integrarea?

Două dependențe: `cryptography>=41.0.0` (pentru sistemul de licențiere) și `beautifulsoup4>=4.12.0` (pentru parsarea răspunsurilor Salesforce). Ambele se instalează automat prin Home Assistant la prima încărcare a integrării.

---

### De ce integrarea folosește Salesforce?

Portalul contulmeu.reteleelectrice.ro este construit pe Salesforce Experience Cloud, folosind Visualforce pages și Aura/Lightning framework. Integrarea emulează un browser pentru a se autentifica și a extrage datele prin aceleași mecanisme pe care le folosește portalul web. Aceasta este singura modalitate de a accesa datele, deoarece Rețele Electrice nu oferă un API public.

---

### Cum raportez o problemă?

1. Activează log-urile de debug (vezi [DEBUG.md](DEBUG.md))
2. Descarcă diagnosticul: **Setări** → **Dispozitive și Servicii** → **Rețele Electrice** → **⋮** → **Descarcă diagnosticul**
3. Deschide un issue pe [GitHub](https://github.com/cnecrea/reteleelectrice/issues) cu log-urile și diagnosticul atașate
