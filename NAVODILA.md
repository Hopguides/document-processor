# Navodila za uporabo sistema

## Hitri začetek

1. **Zagon aplikacije**:
   ```bash
   cd document-processor
   source venv/bin/activate
   python src/main.py
   ```

2. **Dostop**: Odprite http://localhost:5001 v brskalniku

3. **Nastavitev API ključev**:
   - OpenAI API ključ (pridobite na https://platform.openai.com/)
   - Pinecone API ključ (pridobite na https://www.pinecone.io/)
   - Pinecone okolje (npr. us-east-1-aws)

4. **Obdelava dokumenta**:
   - Vnesite besedilo ali naložite datoteko
   - Kliknite "Obdelaj dokument"
   - Počakajte na rezultate

## Pomembne opombe

- Sistem potrebuje veljavne API ključe za delovanje
- Indeks "klemenklon" mora obstajati v Pinecone
- Sistem je optimiziran za 180-stransko dokumentacijo
- Vsi podatki se shranijo v vektorsko bazo za RAG poizvedbe

## Podpora

Za vprašanja ali težave se obrnite na razvijalca sistema.

