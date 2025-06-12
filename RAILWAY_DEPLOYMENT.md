# Railway Deployment Navodila

## Priprava aplikacije za Railway

Vaša Flask aplikacija je pripravljena za deployment na Railway. Sledite tem korakom:

### 1. Ustvarite Railway račun
- Pojdite na https://railway.app
- Registrirajte se ali se prijavite z GitHub računom

### 2. Pripravite projekt za deployment

#### Ustvarite `railway.json` datoteko:
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python src/main.py",
    "healthcheckPath": "/",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

#### Ustvarite `Procfile` datoteko:
```
web: python src/main.py
```

#### Posodobite `src/main.py` za produkcijo:
```python
import os

# Na koncu datoteke zamenjajte:
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### 3. Nastavite okoljske spremenljivke

V Railway dashboard nastavite naslednje okoljske spremenljivke:

- `OPENAI_API_KEY`: Vaš OpenAI API ključ
- `PINECONE_API_KEY`: Vaš Pinecone API ključ  
- `PINECONE_ENVIRONMENT`: Vaše Pinecone okolje (npr. us-east-1-aws)
- `PORT`: 5001 (Railway bo to avtomatsko nastavil)

### 4. Deploy na Railway

#### Možnost A: GitHub integracija (priporočeno)
1. Pushajte kodo na GitHub repository
2. V Railway dashboard kliknite "New Project"
3. Izberite "Deploy from GitHub repo"
4. Izberite vaš repository
5. Railway bo avtomatsko deployala aplikacijo

#### Možnost B: Railway CLI
1. Namestite Railway CLI: `npm install -g @railway/cli`
2. Prijavite se: `railway login`
3. Inicializirajte projekt: `railway init`
4. Deployajte: `railway up`

### 5. Preverite deployment

Po uspešnem deploymentu:
1. Railway vam bo posredoval URL aplikacije
2. Odprite URL v brskalniku
3. Preverite, da se aplikacija naloži
4. Testirajte RAG funkcionalnost

### 6. Upravljanje API ključev

**Pomembno:** Namesto vnosa API ključev preko spletnega vmesnika, uporabite okoljske spremenljivke v Railway za večjo varnost.

Posodobite kodo, da bere ključe iz okoljskih spremenljivk:

```python
# V routes/rag.py dodajte na vrh:
import os

# V _load_api_keys metodi:
def _load_api_keys(self) -> Dict[str, str]:
    # Najprej poskusi okoljske spremenljivke
    env_keys = {
        "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        "pinecone_api_key": os.environ.get("PINECONE_API_KEY"),
        "pinecone_environment": os.environ.get("PINECONE_ENVIRONMENT")
    }
    
    # Če so vsi ključi v okoljskih spremenljivkah, jih uporabi
    if all(env_keys.values()):
        return env_keys
    
    # Sicer preberi iz datoteke (za lokalni razvoj)
    try:
        with open(self.api_keys_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"API ključi niso najdeni")
```

### 7. Monitoring in logs

- V Railway dashboard lahko spremljate logs aplikacije
- Nastavite lahko tudi metrics in alerts
- Za debugging uporabite Railway logs

### 8. Custom domain (opcijsko)

Railway omogoča nastavitev custom domene:
1. V Project Settings kliknite "Domains"
2. Dodajte vašo domeno
3. Nastavite DNS zapise kot prikazano

## Troubleshooting

### Pogosti problemi:

1. **Port napaka**: Prepričajte se, da aplikacija posluša na `0.0.0.0` in portu iz `PORT` okoljske spremenljivke

2. **API ključi**: Preverite, da so okoljske spremenljivke pravilno nastavljene v Railway

3. **Dependencies**: Prepričajte se, da je `requirements.txt` posodobljen z vsemi potrebnimi paketi

4. **Pinecone povezava**: Preverite, da je Pinecone indeks "klemenklon" dostopen iz Railway IP naslovov

### Koristni ukazi:

```bash
# Preveri logs
railway logs

# Odpri shell v Railway
railway shell

# Preveri okoljske spremenljivke
railway variables
```

## Varnost

- Nikoli ne commitajte API ključev v kodo
- Uporabite Railway okoljske spremenljivke za občutljive podatke
- Omogočite HTTPS (Railway to naredi avtomatsko)
- Razmislite o dodatni avtentikaciji za produkcijsko uporabo

