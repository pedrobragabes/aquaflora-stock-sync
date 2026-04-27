"""
AquaFlora Stock Sync - Athos ERP Parser
Parses the "dirty" CSV files exported from Athos ERP.

Supports two input formats:
  1. Clean CSV (preferred): semicolon-separated with header
     "Codigo;CodigoBarras;Descricao;Unidade;Custo;Preco;Preco2;Estoque;
      DepartamentoCod;Departamento;MarcaCod;Marca"
  2. Legacy report (Crystal Reports CSV export): comma-separated with
     repeated header garbage on every row, product data after the
     "Valor Custo" marker.

Crystal Reports binary `.rpt` files are NOT supported and will be rejected.
The legacy CSV format may also contain SKUs corrupted by Excel's float64
rounding (any code with more than 15 significant digits) — the parser
emits warnings and the caller should prefer the clean format.
"""

import logging
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional

import ftfy

from .models import RawProduct
from .exceptions import ParserError

logger = logging.getLogger(__name__)

# IEEE-754 double precision can represent integers exactly up to 2^53 (16 digits).
# Any numeric SKU longer than this MAY have been rounded by spreadsheet tooling.
FLOAT_SAFE_DIGITS = 15

# Sentinel brand values from the ERP that aren't real brands.
BRAND_PLACEHOLDERS = {"", "DIVERSAS", "SEM MARCA", "N/A", "-", "VARIAS"}


class AthosParser:
    """
    Parses dirty Athos ERP export files.

    The Athos ERP exports a report-style "CSV" that includes:
    - Company header information (garbage)
    - Column headers mixed with data
    - Product data after "Valor Custo" marker
    - Totals at the end (garbage)

    This parser identifies the real data and extracts products.
    """

    # Patterns to identify garbage lines
    GARBAGE_PATTERNS = [
        r"^Total\s*(Venda|Custo):",  # Total lines
        r"Página\s*-?\d+\s*de\s*\d+",  # Pagination
        r"^Relatório\s*de\s*Estoque",  # Report headers
        r"^CNPJ:",
        r"^Insc\.\s*Est\.:",
        r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$",  # CNPJ pattern
    ]

    # Header marker - data comes after this column
    HEADER_MARKER = "Valor Custo"

    # Department pattern
    DEPT_PATTERN = r"Departamento:\s*(.+)"

    def __init__(self):
        self._garbage_regex = re.compile(
            "|".join(self.GARBAGE_PATTERNS),
            re.IGNORECASE
        )
        self._dept_regex = re.compile(self.DEPT_PATTERN, re.IGNORECASE)
    
    def parse_file(self, filepath: Path) -> List[RawProduct]:
        """
        Parse an Athos ERP export file and return a list of raw products.

        Supports two formats:
        1. Clean CSV (semicolon-separated, recommended): modern export
        2. Dirty report format: legacy format with "Valor Custo" markers

        Crystal Reports binary `.rpt` files are NOT supported — export
        the same report as CSV from inside Crystal Reports first.

        After parsing, the result is deduplicated by SKU (last row wins)
        and a warning is logged if any duplicates or float-corrupted SKUs
        were detected.

        Args:
            filepath: Path to the CSV/text file.

        Returns:
            List of RawProduct instances (unique by SKU).

        Raises:
            ParserError: If the file cannot be read or parsed, or if a
                Crystal Reports `.rpt` binary is given.
        """
        logger.info(f"📖 Parsing file: {filepath}")

        # Reject Crystal Reports binary up-front — it would otherwise
        # decode to mojibake and silently produce zero products.
        if filepath.suffix.lower() == ".rpt":
            raise ParserError(
                "Crystal Reports .rpt binary files are not supported. "
                "Open the report in Crystal Reports and export it as CSV "
                "(File → Export → CSV) before running the sync.",
                filename=str(filepath),
            )

        # Read file with encoding detection
        try:
            content = self._read_file(filepath)
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"Failed to read file: {e}", filename=str(filepath))

        # Detect format by checking first line
        first_line = content.split('\n')[0] if content else ""

        if "Codigo;CodigoBarras;Descricao" in first_line or ";Descricao;" in first_line:
            # New clean CSV format with semicolon separator
            logger.info("📋 Detected clean CSV format (semicolon-separated)")
            products = self._parse_clean_csv(content, filepath)
        else:
            # Legacy dirty report format
            logger.info("📋 Detected legacy report format")
            logger.warning(
                "⚠️  Legacy CSV format detected. SKUs longer than 15 digits "
                "may have been corrupted by spreadsheet float64 rounding — "
                "prefer the clean semicolon-separated export when available."
            )
            products = self._parse_legacy_format(content, filepath)

        return self._dedupe_and_warn(products)

    def _dedupe_and_warn(self, products: List[RawProduct]) -> List[RawProduct]:
        """
        Deduplicate by SKU (last write wins) and emit warnings.

        - Logs a warning for every SKU that appears more than once,
          showing the conflicting product names so the operator can
          investigate the source file.
        - Logs a warning for any SKU that exceeds the float64 precision
          limit (>15 digits) — these are likely corrupted by Excel.
        """
        if not products:
            return products

        sku_counts = Counter(p.sku for p in products)
        duplicates = {sku: cnt for sku, cnt in sku_counts.items() if cnt > 1}

        if duplicates:
            logger.warning(
                f"⚠️  Found {len(duplicates)} duplicate SKU(s) "
                f"({sum(duplicates.values()) - len(duplicates)} extra rows will be discarded). "
                f"This usually means the source file was opened in Excel and long codes "
                f"were rounded as floats."
            )
            for sku, _ in list(duplicates.items())[:5]:
                names = [p.name for p in products if p.sku == sku]
                logger.warning(f"    SKU {sku}: {names}")

        suspect = [
            p.sku for p in products
            if p.sku.isdigit() and len(p.sku) > FLOAT_SAFE_DIGITS
        ]
        if suspect:
            logger.warning(
                f"⚠️  {len(suspect)} SKU(s) exceed {FLOAT_SAFE_DIGITS} digits and may "
                f"have been corrupted by spreadsheet float rounding. Sample: {suspect[:3]}"
            )

        # Last write wins (matches dict behavior; preserves order via dict)
        seen = {}
        for p in products:
            seen[p.sku] = p
        return list(seen.values())
    
    def _parse_clean_csv(self, content: str, filepath: Path) -> List[RawProduct]:
        """
        Parse the clean CSV format with semicolon separator.

        Column layout (0-indexed):
            0  Codigo            Internal Athos code (zero-padded, e.g. 0000003603)
            1  CodigoBarras      EAN/barcode when present, else short numeric code
            2  Descricao         Product name
            3  Unidade           Unit of measure (UNID, KG, ...)
            4  Custo             Cost (Brazilian decimal: "1,18")
            5  Preco             Sale price
            6  Preco2            Secondary/wholesale price (often "0,00")
            7  Estoque           Stock quantity
            8  DepartamentoCod   Department numeric code
            9  Departamento      Department name (used as category)
           10  MarcaCod          Brand numeric code
           11  Marca             Brand name (may be a placeholder like "DIVERSAS")

        SKU rule: prefer CodigoBarras (col 1). When it's empty or non-numeric,
        fall back to Codigo (col 0) with leading zeros stripped — this keeps
        existing WooCommerce SKUs stable while still handling odd rows.
        """
        products = []
        errors = []

        lines = content.splitlines()
        if not lines:
            return []

        header = lines[0]
        logger.debug(f"CSV Header: {header}")

        # Sanity check: header should contain expected columns. Don't fail
        # hard — just warn so the operator notices if Athos changes the
        # export schema.
        expected = {"codigo", "codigobarras", "descricao", "estoque", "preco"}
        header_lower = header.lower().replace("﻿", "")
        missing = [c for c in expected if c not in header_lower]
        if missing:
            logger.warning(
                f"⚠️  Clean CSV header is missing expected columns {missing}. "
                f"Got: {header[:120]}"
            )

        for line_num, line in enumerate(lines[1:], 2):
            if not line.strip():
                continue

            try:
                cols = line.split(';')
                if len(cols) < 8:
                    continue

                codigo_interno = cols[0].strip()
                ean = cols[1].strip() if len(cols) > 1 else ""
                name = cols[2].strip() if len(cols) > 2 else ""
                cost = cols[4].strip() if len(cols) > 4 else "0"
                price = cols[5].strip() if len(cols) > 5 else "0"
                stock = cols[7].strip() if len(cols) > 7 else "0"
                department = cols[9].strip() if len(cols) > 9 else "SEM_CATEGORIA"
                brand = cols[11].strip() if len(cols) > 11 else ""

                # SKU: prefer EAN/CodigoBarras; fall back to Codigo (unpadded)
                sku = ean if ean and any(c.isdigit() for c in ean) else codigo_interno.lstrip("0")

                if not sku or not any(c.isdigit() for c in sku):
                    continue

                # Only carry EAN forward when it looks like a real barcode
                # (8/12/13/14 digits — UPC/EAN/ITF lengths).
                ean_clean = ean if ean.isdigit() and len(ean) in (8, 12, 13, 14) else None

                product = RawProduct(
                    sku=sku,
                    name=name,
                    stock=stock,
                    minimum="0",
                    price=price,
                    cost=cost,
                    department=department,
                    ean=ean_clean,
                    brand=brand,
                )
                products.append(product)

            except Exception as e:
                errors.append(f"Line {line_num}: {e}")
                logger.debug(f"Line {line_num}: Parse error - {e}")

        logger.info(f"✅ Parsed {len(products)} products from {filepath.name}")
        if errors:
            logger.warning(f"⚠️ {len(errors)} lines had parse errors")

        return products
    
    def _parse_legacy_format(self, content: str, filepath: Path) -> List[RawProduct]:
        """Parse the legacy dirty report format."""
        # Parse each line
        products = []
        errors = []
        
        for line_num, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            
            try:
                parsed = self._parse_line(line)
                if parsed:
                    products.append(parsed)
                    logger.debug(f"Line {line_num}: Parsed product SKU={parsed.sku}")
            except Exception as e:
                errors.append(f"Line {line_num}: {e}")
                logger.debug(f"Line {line_num}: Parse error - {e}")
        
        if errors and not products:
            raise ParserError(
                f"Failed to parse any products. Errors: {errors[:3]}",
                filename=str(filepath)
            )
        
        logger.info(f"✅ Parsed {len(products)} products from {filepath.name}")
        if errors:
            logger.warning(f"⚠️ {len(errors)} lines had parse errors")
        
        return products
    
    def _read_file(self, filepath: Path) -> str:
        """Read file with encoding detection and fix."""
        # Try UTF-8 first, fallback to latin1
        for encoding in ["utf-8", "latin1", "cp1252"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    content = f.read()
                # Fix encoding issues with ftfy
                content = ftfy.fix_text(content)
                logger.debug(f"Successfully read file with encoding: {encoding}")
                return content
            except UnicodeDecodeError:
                continue
        
        raise ParserError(
            f"Could not decode file with any supported encoding (utf-8, latin1, cp1252)",
            filename=str(filepath)
        )
    
    def _parse_line(self, line: str) -> Optional[RawProduct]:
        """
        Parse a single line and extract product if valid.
        
        The line format is comma-separated quoted values.
        We need to find the "Valor Custo" marker and extract
        the product data that comes AFTER it.
        """
        # Split by comma, handling quoted strings
        columns = self._split_csv_line(line)
        
        if len(columns) < 10:
            return None
        
        # Check for garbage lines
        if self._is_garbage_line(columns):
            return None
        
        # Find the header marker position
        header_idx = self._find_header_index(columns)
        if header_idx == -1:
            return None
        
        # Extract department from earlier columns
        department = self._extract_department(columns[:header_idx])
        
        # Product data starts after "Valor Custo"
        # Format: SKU, Description, Stock, Minimum, Price, Cost, ...
        data_start = header_idx + 1
        if len(columns) < data_start + 6:
            return None
        
        try:
            sku = columns[data_start]
            name = columns[data_start + 1]
            stock = columns[data_start + 2]
            minimum = columns[data_start + 3]
            price = columns[data_start + 4]
            cost = columns[data_start + 5]
            
            # Validate SKU (must have at least some digits)
            clean_sku = "".join(c for c in str(sku) if c.isdigit())
            if not clean_sku:
                return None
            
            # Create RawProduct (validation happens in model)
            return RawProduct(
                sku=sku,
                name=name,
                stock=stock,
                minimum=minimum,
                price=price,
                cost=cost,
                department=department,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse product data: {e}")
            return None
    
    def _split_csv_line(self, line: str) -> List[str]:
        """Split CSV line handling quoted values."""
        result = []
        current = []
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                result.append("".join(current).strip().strip('"'))
                current = []
            else:
                current.append(char)
        
        # Don't forget the last field
        if current:
            result.append("".join(current).strip().strip('"'))
        
        return result
    
    def _is_garbage_line(self, columns: List[str]) -> bool:
        """Check if line contains garbage (headers, totals, etc)."""
        combined = " ".join(columns[:5])  # Check first few columns
        return bool(self._garbage_regex.search(combined))
    
    def _find_header_index(self, columns: List[str]) -> int:
        """Find the index of 'Valor Custo' header marker."""
        for i, col in enumerate(columns):
            if col.strip().lower() == self.HEADER_MARKER.lower():
                return i
        return -1
    
    def _extract_department(self, columns: List[str]) -> str:
        """Extract department name from header columns."""
        for col in columns:
            match = self._dept_regex.search(col)
            if match:
                return match.group(1).strip()
        return "SEM_CATEGORIA"


def parse_brazilian_number(value: str) -> float:
    """
    Convert number to float, auto-detecting format:
    - Brazilian: 1.234,56 (dot=thousand, comma=decimal)
    - American:  1,234.56 (comma=thousand, dot=decimal)
    - Simple:    1234.56 or 1234,56
    
    Examples:
        "1.234,56" -> 1234.56
        "1,234.56" -> 1234.56
        "100,00" -> 100.0
        "1000.50" -> 1000.5
        "1000" -> 1000.0
    """
    if not value or (isinstance(value, str) and value.strip() == ""):
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    s = str(value).strip()
    
    # Check for both separators
    has_dot = '.' in s
    has_comma = ',' in s
    
    if has_dot and has_comma:
        # Both separators present - check which comes last (that's the decimal)
        dot_pos = s.rfind('.')
        comma_pos = s.rfind(',')
        
        if comma_pos > dot_pos:
            # Brazilian format: 1.234,56 (comma is decimal)
            cleaned = s.replace(".", "").replace(",", ".")
        else:
            # American format: 1,234.56 (dot is decimal)
            cleaned = s.replace(",", "")
    elif has_comma:
        # Only comma - assume it's decimal (European/Brazilian style)
        cleaned = s.replace(",", ".")
    elif has_dot:
        # Only dot - keep as-is (American format)
        cleaned = s
    else:
        cleaned = s
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
