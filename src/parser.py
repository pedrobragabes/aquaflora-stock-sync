"""
AquaFlora Stock Sync - Athos ERP Parser
Parses the "dirty" CSV files exported from Athos ERP.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import ftfy

from .models import RawProduct
from .exceptions import ParserError

logger = logging.getLogger(__name__)


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
        Parse an Athos ERP export file and return list of raw products.
        
        Supports two formats:
        1. Clean CSV (semicolon-separated): Modern export format
        2. Dirty report format: Legacy format with "Valor Custo" markers
        
        Args:
            filepath: Path to the CSV/text file
            
        Returns:
            List of RawProduct instances
            
        Raises:
            ParserError: If file cannot be read or parsed
        """
        logger.info(f"📖 Parsing file: {filepath}")
        
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
            return self._parse_clean_csv(content, filepath)
        else:
            # Legacy dirty report format
            logger.info("📋 Detected legacy report format")
            return self._parse_legacy_format(content, filepath)
    
    def _parse_clean_csv(self, content: str, filepath: Path) -> List[RawProduct]:
        """Parse the new clean CSV format with semicolon separator."""
        products = []
        errors = []
        
        lines = content.splitlines()
        if not lines:
            return []
        
        # Skip header row
        header = lines[0]
        logger.debug(f"CSV Header: {header}")
        
        for line_num, line in enumerate(lines[1:], 2):
            if not line.strip():
                continue
            
            try:
                cols = line.split(';')
                if len(cols) < 8:
                    continue
                
                # Column mapping for clean CSV:
                # 0: Codigo (Internal code - NOT the SKU!)
                # 1: CodigoBarras (EAN/Barcode - THIS is the SKU for WooCommerce)
                # 2: Descricao (Name)
                # 3: Unidade
                # 4: Custo
                # 5: Preco
                # 6: Preco2
                # 7: Estoque
                # 8: DepartamentoCod
                # 9: Departamento
                # 10: MarcaCod
                # 11: Marca
                
                codigo_interno = cols[0].strip()  # Internal Athos code
                ean = cols[1].strip() if len(cols) > 1 else ""  # This is the real SKU!
                name = cols[2].strip() if len(cols) > 2 else ""
                cost = cols[4].strip() if len(cols) > 4 else "0"
                price = cols[5].strip() if len(cols) > 5 else "0"
                stock = cols[7].strip() if len(cols) > 7 else "0"
                department = cols[9].strip() if len(cols) > 9 else "SEM_CATEGORIA"
                brand = cols[11].strip() if len(cols) > 11 else ""
                
                # SKU = CodigoBarras (EAN), not the internal Athos code!
                sku = ean
                
                # Skip if no valid SKU (EAN)
                if not sku or not any(c.isdigit() for c in sku):
                    continue
                
                product = RawProduct(
                    sku=sku,  # EAN/Barcode
                    name=name,
                    stock=stock,
                    minimum="0",
                    price=price,
                    cost=cost,
                    department=department,
                    ean=ean,  # Same as SKU for reference
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
