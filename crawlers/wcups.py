"""WCUPS (World Checklist of Useful Plant Species) crawler.

Data source: Kew Royal Botanic Gardens — 40,292 useful plant species.
File: data/wcups_2020.pdf (689-page PDF, two-column layout)
Reference: Diazgranados et al. (2020) — EBDCS Level 1 use categories.

Use categories (EBDCS Level 1):
    ME = Materials        MA = Medicines         EU = Environmental Uses
    HF = Human Food       GS = Gene Sources      AF = Animal Food
    PO = Poisons          SU = Social Uses       FU = Fuels
    IF = Invertebrate Food

PDF format: Two-column layout where each species entry consists of:
    Species_name Author
    LSID | USE_CODES [| CWR] [| source_numbers]
Often merged on a single line. Species names and data segments may appear
interleaved across columns.

Requires: pdfplumber (pip install pdfplumber)
"""
import os
import re
import logging
from typing import Generator, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import BaseCrawler

logger = logging.getLogger(__name__)

# EBDCS Level 1 code → human-readable label
USE_CODE_LABELS = {
    'ME': 'Materials',
    'MA': 'Medicines',
    'EU': 'Environmental Uses',
    'HF': 'Human Food',
    'GS': 'Gene Sources',
    'AF': 'Animal Food',
    'PO': 'Poisons',
    'SU': 'Social Uses',
    'FU': 'Fuels',
    'IF': 'Invertebrate Food',
}

_VALID_CODES = set(USE_CODE_LABELS.keys())

# Regex: LSID | USE_CODES [| CWR] [| [source_numbers]]
_DATA_PATTERN = re.compile(
    r'(\d{2,}-\d+|\(in Tropicos\))\s*\|\s*'
    r'([A-Z]{2}(?:\s+[A-Z]{2})*)'
    r'(?:\s*\|\s*CWR)?'
    r'(?:\s*\|\s*\[[^\]]*\])?'
)

# Species data starts at page 12 (index 11) — pages 1-11 are front matter/TOC
_DATA_START_PAGE = 11


def _find_binomial_before(text: str) -> Optional[str]:
    """Find the last binomial (Genus species) in text, reading left to right."""
    words = text.split()
    best = None
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if (len(w1) > 1 and w1[0].isupper() and w1[1:].islower() and
                len(w2) > 1 and w2[0].islower() and
                w1.isalpha()):
            best = f"{w1} {w2}"
    return best


def _find_binomial_after(text: str) -> Optional[str]:
    """Find the first binomial (Genus species) in text."""
    words = text.split()
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if (len(w1) > 1 and w1[0].isupper() and w1[1:].islower() and
                len(w2) > 1 and w2[0].islower() and
                w1.isalpha()):
            return f"{w1} {w2}"
    return None


def parse_wcups_pdf(pdf_path: str, max_pages: int = 0) -> Generator[Dict[str, Any], None, None]:
    """Parse the WCUPS PDF and yield species records.

    Uses a state machine to handle the two-column layout:
    - When a data segment (LSID | CODES) is found, look for the species name
      either inline (before the LSID) or from a pending name from the previous line.
    - When a species name appears after a data segment, store it as pending
      for the next line's data.

    Args:
        pdf_path: Path to the WCUPS PDF file
        max_pages: Max pages to process (0 = all)

    Yields:
        Dict with keys: scientific_name, use_codes, is_cwr
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return

    if not os.path.exists(pdf_path):
        logger.error(f"WCUPS PDF not found: {pdf_path}")
        return

    logger.info(f"Opening WCUPS PDF: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        end_page = total_pages
        if max_pages > 0:
            end_page = min(_DATA_START_PAGE + max_pages, total_pages)

        logger.info(f"Processing pages {_DATA_START_PAGE + 1} to {end_page}")

        count = 0
        species_data = {}  # binomial → {codes: set, is_cwr: bool}
        pending_right = None  # species name from right column awaiting data

        for page_num in range(_DATA_START_PAGE, end_page):
            page = pdf.pages[page_num]
            page_text = page.extract_text()
            if not page_text:
                continue

            for line in page_text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # Skip headers/footers/TOC
                if (line.startswith('World Checklist') or
                        line.startswith('m.diazgranados') or
                        '......' in line):
                    continue
                if re.match(r'^Page \d+ of \d+$', line):
                    continue

                matches = list(_DATA_PATTERN.finditer(line))

                if not matches:
                    # No data on this line — could be a standalone species name
                    binom = _find_binomial_before(line) or _find_binomial_after(line)
                    if binom:
                        pending_right = binom
                    continue

                for m in matches:
                    code_str = m.group(2)
                    is_cwr = 'CWR' in (m.group(0) or '')
                    codes = [c for c in code_str.split() if c in _VALID_CODES]
                    if not codes:
                        continue

                    before = line[:m.start()].strip()
                    after = line[m.end():].strip()

                    species = None

                    # 1. Try name BEFORE data (inline format)
                    if before:
                        species = _find_binomial_before(before)

                    # 2. Use pending species from previous line
                    if not species and pending_right:
                        species = pending_right
                        pending_right = None

                    if species:
                        # Merge codes for this species
                        if species not in species_data:
                            species_data[species] = {
                                'codes': set(),
                                'is_cwr': False,
                            }
                        species_data[species]['codes'].update(codes)
                        if is_cwr:
                            species_data[species]['is_cwr'] = True

                    # Check for species name AFTER data (right column)
                    if after:
                        right_binom = _find_binomial_after(after)
                        if right_binom:
                            pending_right = right_binom

            if (page_num + 1) % 100 == 0:
                logger.info(
                    f"  Page {page_num + 1}/{end_page}: "
                    f"{len(species_data)} species so far"
                )

        # Yield all collected species
        for binomial, data in species_data.items():
            yield {
                'scientific_name': binomial,
                'use_codes': sorted(data['codes']),
                'is_cwr': data['is_cwr'],
            }
            count += 1

        logger.info(f"PDF parsing complete: {count} unique species with use data")


class WCUPSCrawler(BaseCrawler):
    """Crawler for WCUPS (World Checklist of Useful Plant Species).

    Source: Kew 2020 PDF — 40,292 useful plant species
    Data: Use categories (EBDCS Level 1), CWR flag
    """

    name = 'wcups'

    PDF_FILE = 'data/wcups_2020.pdf'

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Parse WCUPS PDF and yield species records."""
        max_records = kwargs.get('max_records', None)
        max_pages = kwargs.get('max_pages', 0)

        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.PDF_FILE
        )

        if not os.path.exists(pdf_path):
            self.logger.error(f"WCUPS PDF not found: {pdf_path}")
            self.logger.info(
                "Download from: https://kew.iro.bl.uk/concern/datasets/"
                "7243d727-e28d-419d-a8f7-9ebef5b9e03e"
            )
            return

        count = 0
        for record in parse_wcups_pdf(pdf_path, max_pages=max_pages):
            yield record
            count += 1
            if max_records and count >= max_records:
                break

    def transform(self, raw_data: Dict) -> Dict:
        """Transform parsed PDF record to internal schema."""
        canonical = raw_data.get('scientific_name', '').strip()
        if not canonical:
            return {}

        return {
            'canonical_name': canonical,
            'use_codes': raw_data.get('use_codes', []),
            'is_cwr': raw_data.get('is_cwr', False),
        }

    def validate(self, data: Dict) -> bool:
        """Require canonical name and at least one use code."""
        return bool(data.get('canonical_name') and data.get('use_codes'))

    def _save(self, data: Dict):
        """Save WCUPS use data to species_uses table."""
        canonical_name = data['canonical_name']
        use_codes = data['use_codes']
        is_cwr = data.get('is_cwr', False)

        with Session(self.engine) as session:
            result = session.execute(
                text("SELECT id FROM species WHERE canonical_name = :name"),
                {'name': canonical_name}
            ).fetchone()

            if not result:
                self.stats['skipped'] += 1
                return

            species_id = result[0]

            inserted_any = False
            for code in use_codes:
                label = USE_CODE_LABELS.get(code, code)
                savepoint = session.begin_nested()
                try:
                    session.execute(
                        text("""
                            INSERT INTO species_uses
                                (species_id, use_code, use_label, is_cwr, source)
                            VALUES (:sid, :code, :label, :cwr, :src)
                            ON CONFLICT (species_id, use_code, source) DO UPDATE SET
                                use_label = EXCLUDED.use_label,
                                is_cwr = EXCLUDED.is_cwr
                        """),
                        {
                            'sid': species_id,
                            'code': code,
                            'label': label,
                            'cwr': is_cwr,
                            'src': self.name,
                        }
                    )
                    savepoint.commit()
                    inserted_any = True
                except Exception as e:
                    savepoint.rollback()
                    self.logger.debug(f"Skip use {code} for {canonical_name}: {e}")

            if inserted_any:
                self.stats['updated'] += 1
            else:
                self.stats['skipped'] += 1

            session.commit()

    def get_use_stats(self) -> Dict:
        """Get statistics about use category coverage."""
        with Session(self.engine) as session:
            result = session.execute(text("""
                SELECT use_code, use_label, COUNT(DISTINCT species_id) as n_species
                FROM species_uses
                WHERE source = 'wcups'
                GROUP BY use_code, use_label
                ORDER BY n_species DESC
            """)).fetchall()

            return {
                'by_category': {
                    row[0]: {'label': row[1], 'count': row[2]} for row in result
                },
                'total_species': session.execute(text(
                    "SELECT COUNT(DISTINCT species_id) FROM species_uses WHERE source = 'wcups'"
                )).scalar() or 0,
            }
