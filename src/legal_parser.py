"""
Parser za slovenske pravne dokumente.
Razbije zakone, pravilnike, poslovnike in druge akte na posamezne člene
z bogatimi metapodatki za uporabo v RAG sistemu.
"""
import re
import json
import os
from typing import List, Dict, Optional, Tuple


class SlovenianLegalParser:
    """
    Parsira slovenske pravne dokumente po njihovi naravni strukturi:
    - Poglavje (chapter): I., II., III. ali rimske številke z naslovom
    - Člen (article): "1. člen", "2. člen" ali samo "člen" z naslovom
    - Odstavek (paragraph): (1), (2), (3) znotraj člena
    - Točka/alineja: 1., 2. ali – znotraj odstavka
    """

    # Regex vzorci za slovensko pravno besedilo
    NUMBERED_ARTICLE = re.compile(r'^(\d+)\.\s*člen\b', re.MULTILINE)
    UNNUMBERED_ARTICLE = re.compile(r'^\s*člen\s*$', re.MULTILINE)
    ARTICLE_TITLE = re.compile(r'^\(([^)]+)\)\s*$', re.MULTILINE)
    PARAGRAPH_NUM = re.compile(r'^\((\d+)\)')
    CHAPTER_ROMAN = re.compile(
        r'^(I{1,3}V?|VI{0,3}|IX|X{1,3})\.\s+(.+)$', re.MULTILINE
    )

    def extract_text_from_file(self, filepath: str) -> str:
        """Izvleče besedilo iz datoteke (.md, .docx, .pdf)."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.md' or ext == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()

        elif ext == '.docx':
            return self._extract_docx(filepath)

        elif ext == '.pdf':
            return self._extract_pdf(filepath)

        else:
            raise ValueError(f"Nepodprt format: {ext}")

    def _extract_docx(self, filepath: str) -> str:
        """Izvleče besedilo iz .docx z ohranjeno strukturo."""
        from docx import Document
        doc = Document(filepath)
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                lines.append('')
                continue
            style = para.style.name.lower() if para.style else ''
            # Alineje (dash items) ohranimo s prefix
            if 'alinea' in style and text.startswith('-'):
                lines.append(text)
            else:
                lines.append(text)
        return '\n'.join(lines)

    def _extract_pdf(self, filepath: str) -> str:
        """Izvleče besedilo iz .pdf."""
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n'.join(pages)

    def parse_document(self, filepath: str, doc_meta: Dict) -> List[Dict]:
        """
        Glavna funkcija: parsira dokument v strukturirane chunk-e.

        Args:
            filepath: Pot do datoteke
            doc_meta: Metapodatki dokumenta:
                - document_name: "Poslovnik Državnega sveta (PoDS-1)"
                - document_abbreviation: "PoDS-1"
                - document_type: "poslovnik" | "zakon" | "pravilnik" | "sklep" | "qa"

        Returns:
            Seznam chunk-ov z metapodatki
        """
        text = self.extract_text_from_file(filepath)
        doc_type = doc_meta.get('document_type', 'zakon')

        if doc_type == 'qa':
            return self._parse_qa_document(text, doc_meta, filepath)

        # Poizkusi najti številčene člene
        numbered_matches = list(self.NUMBERED_ARTICLE.finditer(text))
        # Preštej tudi nenumerirane "člen" vrstice
        unnumbered_matches = list(self.UNNUMBERED_ARTICLE.finditer(text))

        # Če ima oboje (mešan format) ali samo nenumerirane, uporabi unified parser
        if unnumbered_matches and (not numbered_matches or len(unnumbered_matches) > 2):
            chunks = self._parse_unnumbered_articles(text, doc_meta, filepath)
        elif numbered_matches:
            chunks = self._parse_numbered_articles(text, numbered_matches, doc_meta, filepath)
        else:
            # Nima člankov — obravnavaj kot en chunk
            chunks = [{
                "chunk_id": f"{doc_meta['document_abbreviation']}-celota",
                "content": text,
                "metadata": {
                    "document_name": doc_meta["document_name"],
                    "document_abbreviation": doc_meta["document_abbreviation"],
                    "document_type": doc_meta["document_type"],
                    "article_number": 0,
                    "article_title": "",
                    "chapter": "",
                    "paragraph_count": 0,
                    "paragraph_numbers": [],
                    "source_file": os.path.basename(filepath),
                    "cross_references": [],
                }
            }]

        # Dodaj summary chunk za dokument
        if chunks:
            summary = self._create_summary_chunk(chunks, doc_meta, filepath)
            chunks.insert(0, summary)

        return chunks

    def _parse_numbered_articles(
        self, text: str, matches: list, doc_meta: Dict, filepath: str
    ) -> List[Dict]:
        """Parsira dokument s številčenimi členi (1. člen, 2. člen, ...)."""
        chunks = []
        current_chapter = ""

        for i, match in enumerate(matches):
            article_num = int(match.group(1))
            start = match.start()

            # Konec člena = začetek naslednjega ali konec dokumenta
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)

            article_text = text[start:end].strip()

            # Zaznaj poglavje pred tem členom
            chapter = self._find_chapter_before(text, start)
            if chapter:
                current_chapter = chapter

            # Zaznaj naslov člena v oklepajih
            title = self._extract_article_title(article_text)

            # Preštej odstavke
            paragraphs = self._count_paragraphs(article_text)

            chunk_id = f"{doc_meta['document_abbreviation']}-clen-{article_num}"

            chunks.append({
                "chunk_id": chunk_id,
                "content": article_text,
                "metadata": {
                    "document_name": doc_meta["document_name"],
                    "document_abbreviation": doc_meta["document_abbreviation"],
                    "document_type": doc_meta["document_type"],
                    "article_number": article_num,
                    "article_title": title or "",
                    "chapter": current_chapter,
                    "paragraph_count": len(paragraphs),
                    "paragraph_numbers": paragraphs,
                    "source_file": os.path.basename(filepath),
                    "cross_references": self._find_cross_references(article_text),
                }
            })

        # Razbij predolge člene
        chunks = self._split_long_chunks(chunks)

        return chunks

    def _parse_unnumbered_articles(
        self, text: str, doc_meta: Dict, filepath: str
    ) -> List[Dict]:
        """Parsira dokument z nenumeričnimi in/ali mešano numeričnimi členi."""
        lines = text.split('\n')
        articles = []
        current_article_lines = []
        article_counter = 0
        current_chapter = ""
        in_preamble = True

        for line in lines:
            stripped = line.strip()

            # Zaznaj poglavje (rimske številke ali "1. NASLOV POGLAVJA")
            chapter_match = self.CHAPTER_ROMAN.match(stripped)
            if chapter_match:
                current_chapter = stripped
            elif re.match(r'^(\d+)\.\s+[A-ZČŠŽ][A-ZČŠŽ\s]+$', stripped):
                current_chapter = stripped

            # Ali je to začetek novega člena?
            numbered_match = re.match(r'^(\d+)\.\s*člen\b', stripped)
            is_article_start = (
                stripped == 'člen' or
                numbered_match is not None
            )

            if is_article_start:
                in_preamble = False
                # Shrani prejšnji člen
                if current_article_lines and article_counter > 0:
                    articles.append((article_counter, current_chapter, current_article_lines))
                # Če ima eksplicitno številko, jo uporabi
                if numbered_match:
                    article_counter = int(numbered_match.group(1))
                else:
                    article_counter += 1
                current_article_lines = [stripped]
            elif not in_preamble:
                current_article_lines.append(stripped)

        # Zadnji člen
        if current_article_lines and article_counter > 0:
            articles.append((article_counter, current_chapter, current_article_lines))

        chunks = []
        for num, chapter, lines_list in articles:
            article_text = '\n'.join(lines_list)
            title = self._extract_article_title(article_text)
            paragraphs = self._count_paragraphs(article_text)

            chunk_id = f"{doc_meta['document_abbreviation']}-clen-{num}"

            chunks.append({
                "chunk_id": chunk_id,
                "content": article_text,
                "metadata": {
                    "document_name": doc_meta["document_name"],
                    "document_abbreviation": doc_meta["document_abbreviation"],
                    "document_type": doc_meta["document_type"],
                    "article_number": num,
                    "article_title": title or "",
                    "chapter": chapter,
                    "paragraph_count": len(paragraphs),
                    "paragraph_numbers": paragraphs,
                    "source_file": os.path.basename(filepath),
                    "cross_references": self._find_cross_references(article_text),
                }
            })

        chunks = self._split_long_chunks(chunks)
        return chunks

    def _parse_qa_document(
        self, text: str, doc_meta: Dict, filepath: str
    ) -> List[Dict]:
        """Parsira Q&A dokument v pare vprašanje-odgovor."""
        lines = text.split('\n')
        chunks = []
        qa_pairs = []
        current_q = None
        current_a_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Hevristika: vprašanja se končajo z ?
            if stripped.endswith('?'):
                if current_q and current_a_lines:
                    qa_pairs.append((current_q, '\n'.join(current_a_lines)))
                current_q = stripped
                current_a_lines = []
            elif current_q is not None:
                current_a_lines.append(stripped)

        # Zadnji par
        if current_q and current_a_lines:
            qa_pairs.append((current_q, '\n'.join(current_a_lines)))

        for i, (question, answer) in enumerate(qa_pairs, 1):
            chunks.append({
                "chunk_id": f"{doc_meta['document_abbreviation']}-qa-{i}",
                "content": f"Vprašanje: {question}\nOdgovor: {answer}",
                "metadata": {
                    "document_name": doc_meta["document_name"],
                    "document_abbreviation": doc_meta["document_abbreviation"],
                    "document_type": "qa",
                    "article_number": 0,
                    "article_title": question[:80],
                    "chapter": "",
                    "paragraph_count": 0,
                    "paragraph_numbers": [],
                    "source_file": os.path.basename(filepath),
                    "cross_references": self._find_cross_references(answer),
                }
            })

        return chunks

    def _find_chapter_before(self, text: str, position: int) -> str:
        """Najde naslov poglavja pred dano pozicijo v besedilu."""
        # Poišči vse poglavja pred to pozicijo
        chapters = []
        for match in self.CHAPTER_ROMAN.finditer(text[:position]):
            chapters.append(match.group(0))

        # Tudi naslove oblike "1. SPLOŠNE DOLOČBE", "2. KONSTITUIRANJE"
        numbered_chapters = re.finditer(
            r'^(\d+)\.\s+([A-ZČŠŽ][A-ZČŠŽ\s]+)$',
            text[:position],
            re.MULTILINE
        )
        for match in numbered_chapters:
            chapters.append(match.group(0))

        return chapters[-1] if chapters else ""

    def _extract_article_title(self, article_text: str) -> Optional[str]:
        """Izvleče naslov člena v oklepajih, npr. (naloge predsednika)."""
        match = self.ARTICLE_TITLE.search(article_text[:300])
        return match.group(1) if match else None

    def _count_paragraphs(self, article_text: str) -> List[int]:
        """Prešteje in vrne številke odstavkov v členu."""
        paragraphs = []
        for match in re.finditer(r'^\((\d+)\)', article_text, re.MULTILINE):
            paragraphs.append(int(match.group(1)))
        return paragraphs

    def _find_cross_references(self, text: str) -> List[str]:
        """Najde sklicevanja na druge člene/dokumente v besedilu."""
        refs = set()

        # "X. člen [dokumenta]" ali "X. členu"
        for match in re.finditer(r'(\d+)\.\s*člen[uaom]*\b(?:\s+(\w+))?', text):
            article = match.group(1)
            doc_ref = match.group(2) or ""
            refs.add(f"{article}. člen {doc_ref}".strip())

        # "v skladu z zakonom", "na podlagi poslovnika"
        for match in re.finditer(
            r'(?:v skladu z|na podlagi|po)\s+([\w\s]+?(?:zakon|poslovnik|pravilnik)\w*)',
            text, re.IGNORECASE
        ):
            refs.add(match.group(1).strip()[:60])

        return list(refs)[:10]  # Omejimo na 10

    def _split_long_chunks(self, chunks: List[Dict], max_size: int = 1500) -> List[Dict]:
        """Razbije predolge člene na manjše dele po odstavkih ali po vrsticah."""
        result = []
        for chunk in chunks:
            content = chunk["content"]
            if len(content) <= max_size:
                result.append(chunk)
                continue

            # Najprej poskusi razbiti po odstavkih
            parts = re.split(r'(?=^\(\d+\))', content, flags=re.MULTILINE)

            # Če ni odstavkov, razbij po dvojnih praznih vrsticah ali po vrsticah
            if len(parts) <= 1:
                parts = content.split('\n\n')
            if len(parts) <= 1:
                # Zadnja možnost: razbij po fiksni velikosti (po vrsticah)
                lines = content.split('\n')
                parts = []
                current = []
                current_len = 0
                for line in lines:
                    if current_len + len(line) > max_size and current:
                        parts.append('\n'.join(current))
                        current = [line]
                        current_len = len(line)
                    else:
                        current.append(line)
                        current_len += len(line)
                if current:
                    parts.append('\n'.join(current))

            # Ohrani glavo člena (prvi del ali prva vrstica)
            header_match = re.match(r'^(\d+\.\s*člen(?:\n\([^)]+\))?)', content)
            header = header_match.group(1) if header_match else ""

            meta = chunk["metadata"].copy()
            current_content = ""
            part_num = 1
            sub_chunks = []

            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if len(current_content) + len(part) > max_size and current_content:
                    sub_chunks.append(current_content)
                    current_content = (header + "\n" + part) if header and part_num > 1 else part
                    part_num += 1
                else:
                    current_content = (current_content + "\n\n" + part).strip() if current_content else part

            if current_content.strip():
                sub_chunks.append(current_content)

            for i, sub_content in enumerate(sub_chunks):
                sub_meta = meta.copy()
                sub_id = f"{chunk['chunk_id']}-del-{i+1}" if len(sub_chunks) > 1 else chunk['chunk_id']
                result.append({
                    "chunk_id": sub_id,
                    "content": sub_content,
                    "metadata": sub_meta,
                })

        return result

    def _create_summary_chunk(
        self, chunks: List[Dict], doc_meta: Dict, filepath: str
    ) -> Dict:
        """Ustvari povzetek dokument z seznamom vseh členov."""
        article_list = []
        for chunk in chunks:
            meta = chunk["metadata"]
            num = meta.get("article_number", 0)
            title = meta.get("article_title", "")
            if num > 0:
                entry = f"  {num}. člen"
                if title:
                    entry += f" ({title})"
                article_list.append(entry)

        summary_text = (
            f"POVZETEK DOKUMENTA: {doc_meta['document_name']}\n"
            f"Tip: {doc_meta['document_type']}\n"
            f"Število členov: {len(article_list)}\n\n"
            f"Seznam členov:\n" + '\n'.join(article_list)
        )

        return {
            "chunk_id": f"{doc_meta['document_abbreviation']}-povzetek",
            "content": summary_text,
            "metadata": {
                "document_name": doc_meta["document_name"],
                "document_abbreviation": doc_meta["document_abbreviation"],
                "document_type": doc_meta["document_type"],
                "article_number": 0,
                "article_title": "POVZETEK",
                "chapter": "",
                "paragraph_count": 0,
                "paragraph_numbers": [],
                "source_file": os.path.basename(filepath),
                "cross_references": [],
                "is_summary": True,
            }
        }


def parse_mixed_md_file(filepath: str, parser: SlovenianLegalParser) -> List[Dict]:
    """
    Posebna funkcija za parsiranje drzavnisvet.md ki vsebuje
    več dokumentov v eni datoteki:
    - Vrstice 1-68: Opis DS (sestava, pravni okvir)
    - Vrstice 72-161: Seznam internih aktov (samo naslovi)
    - Vrstice 162+: ZSTSPJS celoten zakon
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        full_text = f.read()

    chunks = []

    # 1. Opis DS kot en chunk (prve ~68 vrstic pred "NAZIV INTERNEGA AKTA")
    internal_acts_marker = "NAZIV INTERNEGA AKTA"
    split_pos = full_text.find(internal_acts_marker)

    if split_pos > 0:
        ds_overview = full_text[:split_pos].strip()
        # Razbij pregled po sekcijah (prazne vrstice)
        sections = [s.strip() for s in ds_overview.split('\n\n') if s.strip()]
        for i, section in enumerate(sections, 1):
            chunks.append({
                "chunk_id": f"DS-pregled-{i}",
                "content": section,
                "metadata": {
                    "document_name": "Pregled Državnega sveta RS",
                    "document_abbreviation": "DS-pregled",
                    "document_type": "pregled",
                    "article_number": 0,
                    "article_title": "Sestava in pravni okvir DS",
                    "chapter": "",
                    "paragraph_count": 0,
                    "paragraph_numbers": [],
                    "source_file": os.path.basename(filepath),
                    "cross_references": [],
                }
            })

    # 2. Seznam internih aktov
    uradni_list_marker = "Uradni list"
    uradni_pos = full_text.find(uradni_list_marker, split_pos if split_pos > 0 else 0)

    if split_pos > 0 and uradni_pos > split_pos:
        internal_acts = full_text[split_pos:uradni_pos].strip()
        chunks.append({
            "chunk_id": "DS-interni-akti",
            "content": internal_acts,
            "metadata": {
                "document_name": "Seznam internih aktov DS",
                "document_abbreviation": "DS-interni-akti",
                "document_type": "seznam",
                "article_number": 0,
                "article_title": "Seznam vseh internih aktov DS",
                "chapter": "",
                "paragraph_count": 0,
                "paragraph_numbers": [],
                "source_file": os.path.basename(filepath),
                "cross_references": [],
            }
        })

    # 3. ZSTSPJS - parsaj po členih
    # Najdi začetek zakona (npr. "Z A K O N" ali "1. člen")
    zakon_start = full_text.find("Z A K O N")
    if zakon_start < 0:
        # Poskusi najti prvi člen po uradnem listu
        first_article = re.search(r'^1\.\s*člen', full_text[uradni_pos:], re.MULTILINE)
        if first_article:
            zakon_start = uradni_pos + first_article.start()

    if zakon_start > 0:
        zakon_text = full_text[zakon_start:]
        # Najdi naslov zakona
        naslov_match = re.search(r'O\s+(.+?)(?:\n|$)', zakon_text[:500])

        zstspjs_meta = {
            "document_name": "Zakon o skupnih temeljih sistema plač v javnem sektorju (ZSTSPJS)",
            "document_abbreviation": "ZSTSPJS",
            "document_type": "zakon",
        }

        numbered_matches = list(parser.NUMBERED_ARTICLE.finditer(zakon_text))
        if numbered_matches:
            zstspjs_chunks = parser._parse_numbered_articles(
                zakon_text, numbered_matches, zstspjs_meta, filepath
            )
            if zstspjs_chunks:
                summary = parser._create_summary_chunk(zstspjs_chunks, zstspjs_meta, filepath)
                chunks.append(summary)
                chunks.extend(zstspjs_chunks)

    return chunks
