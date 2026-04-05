# SETUP — Ghid complet de instalare și configurare

Acest ghid detaliază pașii de instalare, configurare inițială, reconfigurare și activare a licenței pentru integrarea **Rețele Electrice** în Home Assistant.

---

## Cerințe preliminare

Înainte de instalare, asigură-te că ai:

- **Home Assistant** versiunea 2024.x sau mai nouă (necesită pattern-ul `entry.runtime_data`)
- **Cont Rețele Electrice** activ — cel de pe portalul contulmeu.reteleelectrice.ro (email + parolă)
- **Licență** validă — [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)
- **Conexiune la internet** — integrarea comunică cu portalul Salesforce al Rețele Electrice pentru date și cu serverul de licențiere

---

## Instalare prin HACS (recomandat)

1. Deschide **HACS** din meniul lateral Home Assistant
2. Navighează la **Integrări**
3. Click pe cele 3 puncte (⋮) din colțul dreapta-sus → **Depozite personalizate** (Custom repositories)
4. Adaugă URL-ul: `https://github.com/cnecrea/reteleelectrice`
5. Selectează categoria: **Integrare** (Integration)
6. Click **Adaugă** (Add)
7. Găsește „**Rețele Electrice**" în lista de integrări → click **Instalează** (Install)
8. **Restartează Home Assistant** — obligatoriu pentru încărcarea integrării

---

## Instalare manuală

1. Descarcă ultima versiune de pe [GitHub Releases](https://github.com/cnecrea/reteleelectrice/releases)
2. Extrage arhiva și copiază folderul `custom_components/reteleelectrice/` în directorul `config/custom_components/` al instalării Home Assistant
3. Structura corectă ar trebui să fie:
   ```
   config/
   └── custom_components/
       └── reteleelectrice/
           ├── __init__.py
           ├── api.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── diagnostics.py
           ├── helpers.py
           ├── license.py
           ├── manifest.json
           ├── sensor.py
           ├── strings.json
           ├── translations/
           └── brand/
   ```
4. **Restartează Home Assistant**

---

## Configurare inițială

### Pasul 1 — Adaugă integrarea

1. Mergi la **Setări** → **Dispozitive și Servicii** → **Adaugă Integrare**
2. Caută „**Rețele Electrice**" (sau „reteleelectrice")
3. Completează formularul de autentificare:

| Câmp | Descriere | Valoare implicită |
|------|-----------|-------------------|
| **Email** | Email-ul contului contulmeu.reteleelectrice.ro | — (obligatoriu) |
| **Parolă** | Parola contului Rețele Electrice | — (obligatoriu) |
| **Interval actualizare** | Câte secunde între actualizări | `3600` (1 oră) |

### Pasul 2 — Selectare puncte de consum (POD)

După autentificarea reușită, se afișează lista POD-urilor descoperite în cont:

- **Monitorizează toate punctele de consum** — activează pentru a urmări automat toate POD-urile
- **Selectare individuală** — alege doar POD-urile pe care vrei să le monitorizezi

Trebuie să selectezi cel puțin un POD sau să activezi opțiunea pentru toate.

### Pasul 3 — Validare și prima actualizare

La apăsarea butonului „Trimite":

- Integrarea creează config entry-ul cu POD-urile selectate
- Coordinator-ul aduce toate datele per POD: detalii contract, citiri contor, arhivă, întreruperi, smart meter
- Senzorii sunt creați automat — câte un device per POD cu toți senzorii aferenți
- Senzorii de producție apar doar pentru POD-uri de tip prosumer
- Senzorii Smart Meter apar doar pentru POD-uri cu contor inteligent

### Pasul 4 — Licență

Integrarea necesită o **licență validă** pentru a funcționa complet. Fără licență:
- Toți senzorii afișează valoarea „Licență necesară"
- Atributele sunt reduse la `{"attribution": "..."}`
- Datele continuă să fie aduse de la portal, dar nu sunt expuse în senzori

Pentru a introduce licența:
1. **Setări** → **Dispozitive și Servicii**
2. Găsește **Rețele Electrice** → click pe **Configurare** (⚙️)
3. Selectează **Licență**
4. Introdu cheia de licență (format: `RETE-XXXX-XXXX-XXXX-XXXX`)
5. Click **Salvează**

Licențe disponibile la: [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)

---

## Reconfigurare cont

Dacă trebuie să schimbi credențialele sau intervalul de actualizare:

1. **Setări** → **Dispozitive și Servicii** → click pe **Rețele Electrice**
2. Click pe **Configurare** (⚙️)
3. Alege **Setări cont**
4. Modifică email-ul, parola sau intervalul de actualizare
5. Click **Trimite** — integrarea validează noile credențiale
6. Dacă validarea reușește, integrarea se reîncarcă automat cu noile setări

Nu este necesar să ștergi și să adaugi din nou integrarea.

---

## Reconfigurare POD-uri

Dacă vrei să modifici ce puncte de consum monitorizezi:

1. **Setări** → **Dispozitive și Servicii** → click pe **Rețele Electrice**
2. Click pe **Configurare** (⚙️)
3. Alege **Setări cont** → la pasul următor se afișează selecția POD-urilor
4. Actualizează selecția → **Salvează**

---

## Activare licență

Integrarea funcționează cu un sistem de licențiere server-side (v3.3):

### Perioadă de evaluare

La prima instalare, integrarea pornește automat în **perioadă de evaluare** (trial). Senzorii funcționează normal în această perioadă, afișând datele reale din contul Rețele Electrice.

### Activare cheie de licență

1. Obține o cheie de licență de la [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)
2. În Home Assistant: **Setări** → **Dispozitive și Servicii** → **Rețele Electrice** → **Configurare** (⚙️)
3. Alege **Licență**
4. Introdu cheia de licență (format: `RETE-XXXX-XXXX-XXXX-XXXX`)
5. Click **Trimite** — cheia este validată la server

Tipuri de licențe disponibile: lunară, anuală, perpetuă.

### Ce se întâmplă fără licență validă

Dacă licența expiră sau nu este activată după perioada de evaluare:

- Toți senzorii vor afișa valoarea **„Licență necesară"**
- Atributele vor arăta `{"attribution": "..."}`
- Datele continuă să fie aduse de la portal, dar nu sunt expuse în senzori

---

## Interval de actualizare

| Parametru | Valoare |
|-----------|---------|
| Implicit | 3600 secunde (1 oră) |
| Minim | 3600 secunde (1 oră) |
| Maxim | 86400 secunde (24 ore) |

Intervalul se referă la cât de des integrarea interoghează portalul Rețele Electrice pentru date noi. Un interval mai mic de 1 oră nu este permis pentru a evita suprasolicitarea portalului Salesforce.

La fiecare ciclu de actualizare, se aduc **toate datele** per POD: detalii contract, citiri contor, arhivă, întreruperi de curent și date smart meter.

---

## Erori posibile la configurare

| Eroare | Cauza | Soluție |
|--------|-------|---------|
| `Autentificare eșuată` | Email sau parolă greșite | Verifică credențialele de pe contulmeu.reteleelectrice.ro |
| `Autentificare reușită, dar nu s-au găsit date` | Contul nu are POD-uri asociate | Verifică contul pe portal |
| `Trebuie să selectați cel puțin un punct de consum` | Niciun POD selectat | Selectează cel puțin un POD sau activează „toate" |
| `Acest cont Rețele Electrice este deja configurat` | Același email adăugat de două ori | Folosește reconfigurarea în loc de o nouă intrare |
| `Cheie de licență invalidă` | Format greșit sau cheie inexistentă | Verifică formatul: `RETE-XXXX-XXXX-XXXX-XXXX` |
| `Această cheie a fost deja utilizată` | Licență activată pe altă instalare | Contactează suportul sau achiziționează o licență nouă |
| `Cheie de licență expirată` | Licența a expirat | Reînnoiește de la hubinteligent.org |
| `Nu se poate conecta la serverul de licențe` | Probleme de rețea | Verifică conexiunea la internet; reîncearcă |

---

## Dezinstalare

1. **Setări** → **Dispozitive și Servicii** → **Rețele Electrice**
2. Click pe cele 3 puncte (⋮) → **Șterge**
3. Confirmă ștergerea
4. (Opțional) Elimină folderul `custom_components/reteleelectrice/` și restartează Home Assistant
