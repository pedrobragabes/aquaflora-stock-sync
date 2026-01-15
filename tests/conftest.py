"""
AquaFlora Stock Sync - Test Fixtures
Shared fixtures for pytest tests.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import RawProduct, EnrichedProduct
from src.database import ProductDatabase


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_raw_product() -> RawProduct:
    """Sample RawProduct for testing."""
    return RawProduct(
        sku="12345",
        name="RACAO ROYAL CANIN MINI ADULT 7,5KG",
        stock=10,
        minimum=2,
        price=289.90,
        cost=200.00,
        department="PET_RACOES",
    )


@pytest.fixture
def sample_raw_product_brazilian_format() -> dict:
    """Raw data with Brazilian number format."""
    return {
        "sku": "67890",
        "name": "ANTIPULGAS BRAVECTO 10-20KG",
        "stock": "5",
        "minimum": "1",
        "price": "1.234,56",  # Brazilian format
        "cost": "800,00",     # Brazilian format
        "department": "VETERINARIA",
    }


@pytest.fixture
def sample_enriched_product() -> EnrichedProduct:
    """Sample EnrichedProduct for testing."""
    return EnrichedProduct(
        sku="12345",
        name="Ração Royal Canin Mini Adult 7,5kg",
        name_original="RACAO ROYAL CANIN MINI ADULT 7,5KG",
        stock=10,
        price=Decimal("289.90"),
        cost=Decimal("200.00"),
        minimum=2,
        category="Pet Rações",
        category_original="PET_RACOES",
        brand="Royal Canin",
        weight_kg=7.5,
        short_description="Ração Royal Canin Mini Adult 7,5kg | Marca: Royal Canin | Categoria: Pet Rações | AquaFlora Agroshop",
        description="<div>Produto Royal Canin...</div>",
        tags=["Pet Rações", "Royal Canin", "Premium"],
        published=True,
    )


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture
def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    db = ProductDatabase(db_path)
    yield db
    
    # Cleanup
    db.close()
    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def populated_database(temp_database, sample_enriched_product):
    """Database with some sample data."""
    db = temp_database
    
    # Save a product
    db.save_sync_result(
        sku=sample_enriched_product.sku,
        woo_id=1001,
        hash_full=sample_enriched_product.hash_full,
        hash_fast=sample_enriched_product.hash_fast,
        price=float(sample_enriched_product.price),
    )
    
    # Mark as existing on site
    db.save_from_woocommerce("12345", 1001)
    
    return db


# =============================================================================
# FILE FIXTURES
# =============================================================================

@pytest.fixture
def sample_csv_content() -> str:
    """Sample CSV content in Athos ERP format."""
    return '''\"AquaFlora Agroshop Ltda\",\"CNPJ: 12.345.678/0001-00\"
\"Relatório de Estoque\",\"Página 1 de 1\"
\"Departamento: PET_RACOES\",\"Estoque\",\"Est Min\",\"Preco\",\"Valor Custo\",\"12345\",\"RACAO ROYAL CANIN MINI ADULT 7,5KG\",\"10\",\"2\",\"289,90\",\"200,00\"
\"Departamento: VETERINARIA\",\"Estoque\",\"Est Min\",\"Preco\",\"Valor Custo\",\"67890\",\"ANTIPULGAS BRAVECTO 10-20KG\",\"5\",\"1\",\"180,00\",\"120,00\"
\"Total Venda:\",\"469,90\"
'''


@pytest.fixture
def sample_csv_file(sample_csv_content, tmp_path) -> Path:
    """Create a temporary CSV file for testing."""
    csv_file = tmp_path / "test_estoque.csv"
    csv_file.write_text(sample_csv_content, encoding="utf-8")
    return csv_file
