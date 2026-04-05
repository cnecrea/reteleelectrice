# DEBUG — Ghid de depanare

Ghid pentru identificarea și rezolvarea problemelor cu integrarea **Rețele Electrice** în Home Assistant.

---

## Activare log-uri de debug

Adaugă în `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.reteleelectrice: debug
```

Restartează Home Assistant. Log-urile vor apărea în **Setări** → **Sistem** → **Jurnale** (Logs), sau în fișierul `home-assistant.log`.

Pentru a vizualiza doar log-urile Rețele Electrice:

```
grep -i "reteleelectrice\|ReteleElectrice" config/home-assistant.log
```

---

## Descărcare diagnostic

Integrarea include suport pentru export diagnostic:

1. **Setări** → **Dispozitive și Servicii** → **Rețele Electrice**
2. Click pe cele 3 puncte (⋮) → **Descarcă diagnosticul**

Fișierul JSON conține informații despre configurare, starea licenței, starea coordinator-ului și lista senzorilor activi. Datele sensibile (parolă, token-uri, sesiune Salesforce) sunt excluse automat.

---

## Probleme frecvente

### Integrarea nu apare în lista de integrări

**Cauza**: Folderul `custom_components/reteleelectrice/` nu este în locația corectă sau Home Assistant nu a fost restartat.

**Soluție**:
1. Verifică structura: `config/custom_components/reteleelectrice/__init__.py` trebuie să existe
2. Verifică `manifest.json` — domeniul trebuie să fie `reteleelectrice`
3. Restartează Home Assistant complet (nu doar reîncarcă configurația)
4. Verifică log-urile pentru erori de import:
   ```
   grep -i "reteleelectrice" config/home-assistant.log | grep -i "error"
   ```

---

### „Autentificare eșuată" la configurare

**Cauza**: Email sau parolă incorecte, sau probleme cu portalul Salesforce.

**Soluție**:
1. Verifică că folosești credențialele de pe contulmeu.reteleelectrice.ro (nu cele de la un furnizor de energie)
2. Testează login-ul direct pe portalul [contulmeu.reteleelectrice.ro](https://contulmeu.reteleelectrice.ro)
3. Verifică dacă contul nu e blocat sau necesită verificare suplimentară
4. Verifică log-urile de debug:
   ```
   grep "ReteleElectrice.*ConfigFlow\|ReteleElectrice.*auth" config/home-assistant.log
   ```

---

### „Autentificare reușită, dar nu s-au găsit date"

**Cauza**: Contul există pe portal dar nu are niciun POD (punct de consum) asociat.

**Soluție**:
1. Autentifică-te pe [contulmeu.reteleelectrice.ro](https://contulmeu.reteleelectrice.ro) și verifică dacă ai POD-uri vizibile
2. Dacă ai adăugat recent un POD pe portal, poate dura câteva ore până apare
3. Verifică log-urile:
   ```
   grep "ReteleElectrice.*pods\|ReteleElectrice.*POD" config/home-assistant.log
   ```

---

### Nu se poate conecta la portalul Rețele Electrice

**Cauza**: Probleme de rețea, firewall, sau portalul Salesforce este indisponibil.

**Soluție**:
1. Verifică conexiunea la internet din Home Assistant
2. Testează conectivitatea:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://contulmeu.reteleelectrice.ro/
   ```
3. Verifică dacă un firewall sau DNS blochează `contulmeu.reteleelectrice.ro` sau `*.salesforce.com`
4. Reîncearcă după câteva minute — portalul Salesforce poate avea mentenanță

---

### Toți senzorii afișează „Licență necesară"

**Cauza**: Licența nu este activă (trial expirat, licență expirată, sau neactivată).

**Soluție**:
1. Verifică statusul licenței în log-uri:
   ```
   grep "ReteleElectrice.*licen\|ReteleElectrice.*LICENSE" config/home-assistant.log
   ```
2. Activează o licență: OptionsFlow → Licență (vezi [SETUP.md](SETUP.md))
3. Dacă serverul de licențiere e temporar indisponibil, există un grace period — licența anterioară rămâne validă temporar (72 ore pentru licențe active, 24 ore pentru trial)
4. Verifică log-ul pentru erori de comunicare cu serverul de licențiere

---

### „Prima actualizare eșuată" la setup

**Cauza**: Coordinator-ul nu a putut aduce datele de la portalul Rețele Electrice la prima încărcare.

**Soluție**:
1. Verifică log-urile de debug:
   ```
   grep "ReteleElectrice.*eroare\|ReteleElectrice.*eșuat\|ReteleElectrice.*timeout" config/home-assistant.log
   ```
2. Dacă e o eroare de autentificare (`ConfigEntryAuthFailed`), reconfigurează credențialele
3. Dacă e timeout, verifică rețeaua și reîncearcă
4. Portalul Salesforce poate returna erori temporare — reîncearcă mai târziu

---

### Senzorii de producție nu apar

**Cauza**: POD-ul nu este de tip prosumer.

**Soluție**:
1. Senzorii „Index citire producție", „Energie produsă" și „Smart Meter Producție" sunt creați doar pentru POD-uri cu contract de tip **prosumer**
2. Verifică pe portalul contulmeu.reteleelectrice.ro tipul contractului pentru POD-ul respectiv
3. Verifică log-urile:
   ```
   grep "ReteleElectrice.*prosumer\|ReteleElectrice.*productie" config/home-assistant.log
   ```

---

### Senzorii Smart Meter nu apar

**Cauza**: POD-ul nu are contor inteligent (smart meter).

**Soluție**:
1. Senzorii „Smart Meter Consum" și „Smart Meter Producție" sunt creați doar pentru POD-uri cu flag-ul **smart meter** activ
2. Verifică pe portal dacă POD-ul are contor inteligent
3. În log-uri, verifică flag-ul smart meter:
   ```
   grep "ReteleElectrice.*smart\|ReteleElectrice.*Smart" config/home-assistant.log
   ```

---

### Senzorii de valoare instantanee nu se actualizează

**Cauza**: Datele instantanee se aduc la apăsarea butonului de actualizare sau la intervale stabilite de automatizări.

**Soluție**:
1. Senzori „Valoare instantanee consum" și „Valoare instantanee producție" sunt disponibili doar pentru POD-uri cu **smart meter**
2. Pentru actualizare automată, creează o automatizare care apasă butonul periodic (ex: la fiecare oră):
   ```yaml
   automation:
     - alias: "Actualizare valori instantanee"
       trigger:
         - platform: time_pattern
           minutes: "/60"
       action:
         - service: button.press
           target:
             entity_id: button.reteleelectrice_RO001EXXXXXXXXX_actualizare_instantanee
   ```
3. Apasă manual butonul din interfață pentru actualizare imedială
4. Verifică în log-uri dacă sunt erori la interogarea datelor instantanee:
   ```
   grep "ReteleElectrice.*instantanee\|ReteleElectrice.*MeterInstantData" config/home-assistant.log
   ```

---

### Datele furnizorului nu apar

**Cauza**: Datele furnizorului trebuie aduse din endpoint-ul queryPOD al VF Proxy.

**Soluție**:
1. Senzorul „Date furnizor" ar trebui să apară pentru **TOATE POD-urile**, indiferent de tip sau configurare
2. Verifică că integrarea are acces la datele furnizorului:
   ```
   grep "ReteleElectrice.*furnizor\|ReteleElectrice.*queryPOD" config/home-assistant.log
   ```
3. Dacă nu apar, verifică log-urile pentru erori de interogare VF Proxy
4. Reîncarcă integrarea: **⋮** → **Reîncarcă**

---

### Datele nu se actualizează

**Cauza**: Coordinator-ul a intrat în eroare, sesiunea Salesforce a expirat, sau intervalul de actualizare e prea mare.

**Soluție**:
1. Verifică log-urile coordinator-ului:
   ```
   grep "ReteleElectrice.*UpdateFailed\|ReteleElectrice.*AuthFailed" config/home-assistant.log
   ```
2. Verifică `last_update_success` în diagnosticul integrării
3. Reîncarcă integrarea: **⋮** → **Reîncarcă**
4. Dacă problema persistă, verifică dacă portalul funcționează (login pe contulmeu.reteleelectrice.ro)

---

### Licență invalidă

```
[ReteleElectrice:License] Licența nu este validă. Motiv: expired / invalid_key / server_unreachable.
[ReteleElectrice] Integrarea nu are licență validă. Senzorii vor afișa 'Licență necesară'.
```

**Cauza**: Licența a expirat, cheia este greșită, sau serverul de licențe nu este accesibil.

**Rezolvare**:
1. Verifică cheia de licență în OptionsFlow
2. Dacă a expirat, reînnoiește de la [hubinteligent.org/donate?ref=reteleelectrice](https://hubinteligent.org/donate?ref=reteleelectrice)
3. Dacă serverul nu e accesibil, există un grace period — licența rămâne validă temporar

---

### Eroare „cryptography" sau „beautifulsoup4" la prima instalare

**Cauza**: Dependențele nu s-au instalat automat.

**Soluție**:
1. Integrarea declară dependențele în `manifest.json` — Home Assistant le instalează automat
2. Dacă eșuează, instalează manual:
   ```bash
   pip install cryptography>=41.0.0 beautifulsoup4>=4.12.0
   ```
3. Pe Raspberry Pi sau sisteme ARM, compilarea `cryptography` poate dura; folosește `pip install --prefer-binary cryptography`

---

### Eroare de sesiune Salesforce

```
[ReteleElectrice:API] Sesiunea Salesforce a expirat, re-login...
```

**Cauza**: Sesiunea CookieJar a expirat pe server. Comportament normal — integrarea face re-login automat.

**Rezolvare**: Nu necesită intervenție. Dacă re-login-ul eșuează repetat:
1. Verifică credențialele (reconfigurare cont)
2. Verifică dacă portalul este accesibil
3. Verifică dacă IP-ul Home Assistant nu este blocat

---

## Log-uri utile de referință

### Login reușit
```
[ReteleElectrice:API] Login Salesforce reușit
```

### Fetch complet reușit
```
[ReteleElectrice] Se adaugă 12 senzori și 1 buton (entry_id=abc123)
```

### Eroare de rețea
```
[ReteleElectrice:API] Timeout pe VF proxy ReadingArchive (15s)
[ReteleElectrice:API] Eroare rețea: ClientConnectorError
```

### Sesiune reînnoită automat
```
[ReteleElectrice:API] Sesiunea Salesforce a expirat, re-login...
[ReteleElectrice:API] Login Salesforce reușit
```

### Licență — heartbeat
```
[ReteleElectrice:License] Heartbeat OK. Licența este validă (expiră: 2027-01-15).
```

### Licență validă
```
[ReteleElectrice] Licență activă — tip: perpetual
```

### Trial activ
```
[ReteleElectrice] Perioadă de evaluare — 14 zile rămase
```

---

## Contactare suport

Dacă problema persistă:

1. Activează log-urile de debug
2. Reproduce problema
3. Descarcă diagnosticul integrării
4. Deschide un issue pe [GitHub](https://github.com/cnecrea/reteleelectrice/issues) cu:
   - Versiunea Home Assistant
   - Versiunea integrării Rețele Electrice
   - Log-urile relevante (cu date sensibile mascate)
   - Fișierul diagnostic
   - Pași pentru reproducerea problemei
