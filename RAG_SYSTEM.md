# RAG Sistem z uporabniškim vmesnikom

## Pregled

Uspešno sem razširil obstoječi sistem za obdelavo dokumentov z RAG (Retrieval-Augmented Generation) funkcionalnostjo. Sistem sedaj omogoča:

1. **Obdelavo dokumentov** v vektorsko bazo (Pinecone)
2. **RAG poizvedbe** z uporabniškim vmesnikom
3. **Railway deployment** za produkcijsko uporabo

## Nove funkcionalnosti

### 1. RAG API Endpoints

- **`/api/rag/query`** - POST endpoint za RAG poizvedbe
- **`/api/rag/health`** - GET endpoint za preverjanje stanja sistema

### 2. Uporabniški vmesnik

- **Sekcija 5: RAG Poizvedbe** - Vnos vprašanj o dokumentaciji
- **Sekcija 6: Odgovor** - Prikaz odgovorov z viri
- **Avtomatsko preverjanje stanja** sistema ob nalaganju strani

### 3. RAG Sistem

- **Retrieval**: Iskanje relevantnih dokumentov v Pinecone
- **Generation**: Generiranje odgovorov z OpenAI GPT-3.5-turbo
- **Sources**: Prikaz virov, ki so bili uporabljeni za odgovor

## Testiranje

Sistem je bil uspešno testiran:

✅ **RAG poizvedba**: "Kaj je glavna tema dokumentacije?"
✅ **Odgovor**: "Glavna tema dokumentacije je varstvo podatkov in informacijska varnost."
✅ **Viri**: Prikazanih 5 relevantnih virov iz dokumentacije

## Railway Deployment

Aplikacija je pripravljena za deployment na Railway:

- **railway.json** - Konfiguracija za Railway
- **Procfile** - Definicija web procesa
- **Okoljske spremenljivke** - Podpora za varno shranjevanje API ključev
- **Produkcijska konfiguracija** - Optimizirano za Railway

## Struktura projekta

```
document-processor/
├── src/
│   ├── main.py                 # Glavna Flask aplikacija (posodobljena)
│   ├── routes/
│   │   ├── api_keys.py        # API ključi in obdelava dokumentov
│   │   ├── rag.py             # RAG funkcionalnost (novo)
│   │   └── user.py            # Osnovni user endpoints
│   ├── static/
│   │   └── index.html         # Spletni vmesnik (razširjen z RAG)
│   └── models/
│       └── user.py            # Database modeli
├── railway.json               # Railway konfiguracija (novo)
├── Procfile                   # Railway Procfile (novo)
├── RAILWAY_DEPLOYMENT.md      # Navodila za deployment (novo)
├── requirements.txt           # Python odvisnosti
└── README.md                  # Dokumentacija
```

## Uporaba

### Lokalno testiranje
```bash
cd document-processor
source venv/bin/activate
python src/main.py
```

### Railway deployment
1. Pushajte kodo na GitHub
2. Povežite z Railway
3. Nastavite okoljske spremenljivke:
   - `OPENAI_API_KEY`
   - `PINECONE_API_KEY`
   - `PINECONE_ENVIRONMENT`
4. Railway avtomatsko deploya aplikacijo

## Varnost

- API ključi se berejo iz okoljskih spremenljivk (Railway)
- Fallback na lokalno datoteko za razvoj
- CORS omogočen za frontend-backend komunikacijo
- HTTPS avtomatsko omogočen na Railway

## Rezultat

Sistem je pripravljen za produkcijsko uporabo in omogoča:
- Obdelavo dokumentov v vektorsko bazo
- Inteligentne RAG poizvedbe z uporabniškim vmesnikom
- Enostaven deployment na Railway platformo

