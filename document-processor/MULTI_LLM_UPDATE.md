# Multi-LLM RAG System - Posodobitve

## Pregled posodobitev

Uspešno sem razširil RAG sistem z podporo za več LLM ponudnikov. Sedaj lahko uporabniki izbirajo med različnimi AI modeli za generiranje odgovorov.

## Nove funkcionalnosti

### 1. Podpora za več LLM ponudnikov

**Podprti ponudniki:**
- **OpenAI** (GPT-3.5-turbo, GPT-4, GPT-4-turbo)
- **Google Gemini** (gemini-pro, gemini-pro-vision)
- **Anthropic Claude** (claude-3-sonnet, claude-3-haiku)

### 2. Dinamična izbira modelov

- Uporabniški vmesnik se prilagaja dostopnim ponudnikom
- Modeli se posodabljajo glede na izbrani ponudnik
- Sistem avtomatsko zazna dostopne API ključe

### 3. Novi API endpoints

- **`/api/rag/providers`** - Vrne seznam dostopnih ponudnikov in modelov
- **`/api/rag/query`** - Razširjen z možnostjo izbire ponudnika in modela
- **`/api/rag/health`** - Posodobljen z informacijami o dostopnih ponudnikih

### 4. Posodobljen uporabniški vmesnik

- **Dropdown za izbiro ponudnika** - OpenAI, Gemini, Anthropic
- **Dropdown za izbiro modela** - Se posodobi glede na izbrani ponudnik
- **Prikaz ponudnika v odgovoru** - Uporabnik vidi, kateri model je generiral odgovor

## Tehnične izboljšave

### Backend (Flask)

```python
class MultiLLMRAGSystem:
    def _get_llm(self, provider: str = "openai", model: str = None):
        """Vrne LLM glede na ponudnika"""
        if provider == "openai":
            return ChatOpenAI(model=model or "gpt-3.5-turbo")
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(model=model or "gemini-pro")
        elif provider == "anthropic":
            return ChatAnthropic(model=model or "claude-3-sonnet-20240229")
```

### Frontend (JavaScript)

```javascript
async function askQuestion() {
    const provider = document.getElementById('llm-provider').value;
    const model = document.getElementById('llm-model').value;
    
    const response = await fetch('/api/rag/query', {
        method: 'POST',
        body: JSON.stringify({ 
            question: question,
            provider: provider,
            model: model
        })
    });
}
```

## Konfiguracija okoljskih spremenljivk

Za Railway deployment dodajte naslednje okoljske spremenljivke:

### Obvezne (za osnovni OpenAI RAG):
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_ENVIRONMENT`

### Opcijske (za dodatne ponudnike):
- `GOOGLE_API_KEY` - za Google Gemini
- `ANTHROPIC_API_KEY` - za Anthropic Claude

## Prednosti novega sistema

1. **Fleksibilnost** - Uporabniki lahko izbirajo med različnimi AI modeli
2. **Redundanca** - Če en ponudnik ne deluje, lahko uporabijo drugega
3. **Optimizacija stroškov** - Različni modeli imajo različne cene
4. **Primerjava rezultatov** - Možnost testiranja različnih modelov na istih podatkih

## Naslednji koraki

1. **Nastavite dodatne API ključe** v Railway okoljskih spremenljivkah
2. **Testirajte različne ponudnike** na vaši dokumentaciji
3. **Primerjajte kakovost odgovorov** med različnimi modeli

## Opombe

- Embeddings se še vedno ustvarjajo z OpenAI (za konsistentnost)
- Sistem avtomatsko zazna dostopne ponudnike glede na API ključe
- Če ponudnik ni dostopen, se ne prikaže v dropdown meniju

Sistem je pripravljen za deployment na Railway z razširjenimi funkcionalnostmi!

