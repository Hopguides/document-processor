# Strategija testiranja za Railway Deployment

## 1. Cilj testiranja
Preveriti funkcionalnost, varnost in uporabniško izkušnjo aplikacije `document-processor`, ko je nameščena na platformi Railway.

## 2. Predpogoji
- Uspešna namestitev aplikacije na Railway.
- Dostop do URL-ja aplikacije.
- Nastavljene okoljske spremenljivke za API ključe (OpenAI, Pinecone).

## 3. Testni scenariji

### 3.1. Funkcionalno testiranje

#### 3.1.1. Upravljanje API ključev
- **Test 1.1**: Shranjevanje API ključev preko spletnega vmesnika.
  - **Koraki**:
    1. Odpri aplikacijo v brskalniku.
    2. Vnesi veljavne API ključe za OpenAI in Pinecone.
    3. Klikni gumb "Shrani API ključe".
  - **Pričakovan rezultat**: Prikaže se sporočilo o uspešnem shranjevanju.
- **Test 1.2**: Nalaganje shranjenih API ključev.
  - **Koraki**:
    1. Osveži stran.
    2. Klikni gumb "Naloži shranjene ključe".
  - **Pričakovan rezultat**: Vnosna polja se izpolnijo z maskiranimi vrednostmi ključev.

#### 3.1.2. Obdelava dokumentov
- **Test 2.1**: Obdelava dokumenta preko vnosnega polja.
  - **Koraki**:
    1. Vnesi besedilo v polje za vnos besedila.
    2. Klikni gumb "Obdelaj dokument".
  - **Pričakovan rezultat**: Prikaže se sporočilo o uspešni obdelavi z statistiko (število kosov, znakov itd.).
- **Test 2.2**: Obdelava dokumenta preko nalaganja datoteke.
  - **Koraki**:
    1. Izberi datoteko (TXT, PDF, DOCX).
    2. Klikni gumb "Obdelaj dokument".
  - **Pričakovan rezultat**: Prikaže se sporočilo o uspešni obdelavi z statistiko.

#### 3.1.3. RAG poizvedbe
- **Test 3.1**: Pošiljanje vprašanja in prejemanje odgovora.
  - **Koraki**:
    1. Vnesi vprašanje v polje za RAG poizvedbe.
    2. Klikni gumb "Postavi vprašanje".
  - **Pričakovan rezultat**: Prikaže se odgovor, skupaj z viri, uporabljenimi za generiranje odgovora.

### 3.2. Testiranje API končnih točk
Uporabi orodje, kot je `curl` ali Postman, za testiranje naslednjih končnih točk:

- **GET /api/rag/health**: Preveri stanje sistema.
  - **Pričakovan rezultat**: Odgovor JSON z `{"success": true, ...}`.
- **POST /api/save-keys**: Shrani API ključe.
  - **Pričakovan rezultat**: Odgovor JSON z `{"message": "API keys saved successfully"}`.
- **GET /api/load-keys**: Naloži API ključe.
  - **Pričakovan rezultat**: Odgovor JSON z maskiranimi ključi.
- **POST /api/process-document**: Obdelaj dokument.
  - **Pričakovan rezultat**: Odgovor JSON z rezultati obdelave.
- **POST /api/rag/query**: Izvedi RAG poizvedbo.
  - **Pričakovan rezultat**: Odgovor JSON z odgovorom in viri.

### 3.3. Varnostno testiranje
- **Test 4.1**: Preverjanje hrambe ključev.
  - **Opis**: Preveri, da se API ključi ne shranjujejo v javno dostopnih datotekah ali v kodi na odjemalski strani.
  - **Pričakovan rezultat**: Ključi so shranjeni na strežniku in se ne pošiljajo odjemalcu.
- **Test 4.2**: Preverjanje CORS nastavitev.
  - **Opis**: Preveri, da so CORS nastavitve pravilno konfigurirane in dovoljujejo dostop samo iz pooblaščenih domen.
  - **Pričakovan rezultat**: Brskalnik ne poroča o napakah, povezanih s CORS.

### 3.4. Testiranje uporabniške izkušnje
- **Test 5.1**: Responzivnost vmesnika.
  - **Opis**: Preveri, kako se vmesnik prilagaja različnim velikostim zaslona (mobilni telefon, tablica, namizni računalnik).
  - **Pričakovan rezultat**: Vmesnik je uporaben in berljiv na vseh napravah.
- **Test 5.2**: Jasnost sporočil.
  - **Opis**: Preveri, ali so sporočila o napakah in uspehu jasna in razumljiva.
  - **Pričakovan rezultat**: Uporabnik prejme jasne povratne informacije o svojih dejanjih.

## 4. Analiza napak in rešitve

- **Napaka**: Aplikacija se ne zažene na Railway.
  - **Možen vzrok**: Napačno nastavljene okoljske spremenljivke, napaka v kodi, težave z odvisnostmi.
  - **Rešitev**: Preveri Railway loge za podrobnosti o napaki. Preveri, ali so vse odvisnosti v `requirements.txt`.
- **Napaka**: Neuspešna obdelava dokumenta.
  - **Možen vzrok**: Neveljaven API ključ za OpenAI ali Pinecone, napaka pri povezovanju s storitvami.
  - **Rešitev**: Preveri veljavnost API ključev. Preveri stanje storitev OpenAI in Pinecone.

## 5. Poročilo o testiranju
Po končanem testiranju pripravi poročilo, ki vključuje:
- Povzetek rezultatov testiranja.
- Seznam odkritih napak in težav.
- Priporočila za izboljšave (funkcionalne, varnostne, uporabniška izkušnja).
- Oceno pripravljenosti aplikacije za produkcijsko uporabo.
