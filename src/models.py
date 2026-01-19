"""
AquaFlora Stock Sync - Pydantic Models
Data models for products, sync decisions, and API payloads.
"""

from decimal import Decimal
from enum import Enum
from hashlib import md5
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, computed_field


class SyncDecision(str, Enum):
    """Sync decision types based on hash comparison."""
    NEW = "new"               # SKU not in DB → POST full payload
    FULL_UPDATE = "full"      # hash_full changed → PUT full payload
    FAST_UPDATE = "fast"      # only hash_fast changed → PUT price/stock
    SKIP = "skip"             # no changes
    BLOCKED = "blocked"       # blocked by PriceGuard


class RawProduct(BaseModel):
    """Raw product from Athos ERP parser (before enrichment)."""
    sku: str
    name: str
    stock: float
    minimum: float
    price: float
    cost: float
    department: str
    ean: Optional[str] = None  # CodigoBarras from CSV
    brand: Optional[str] = None  # Marca from CSV
    
    @field_validator("sku", mode="before")
    @classmethod
    def clean_sku(cls, v):
        """Remove non-numeric characters from SKU."""
        if v is None:
            return ""
        return "".join(c for c in str(v) if c.isdigit())
    
    @field_validator("stock", "minimum", "price", "cost", mode="before")
    @classmethod
    def parse_brazilian_number(cls, v):
        """
        Convert number to float, auto-detecting format:
        - Brazilian: 1.234,56 (dot=thousand, comma=decimal)
        - American:  1,234.56 (comma=thousand, dot=decimal)
        - Simple:    1234.56 or 1234,56
        """
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        
        s = str(v).strip()
        
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
            # Only dot - check if it's likely a thousand separator or decimal
            # If there are exactly 3 digits after the dot, it's likely thousands
            parts = s.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                # Could be thousand separator (1.234 = 1234)  
                # But also could be price (9.990 = 9990 which is wrong!)
                # Safest: if value looks like it has 2 decimals, treat as decimal
                # Otherwise treat as-is
                cleaned = s  # Keep as American format
            else:
                cleaned = s  # Keep as-is (American format)
        else:
            cleaned = s
        
        try:
            return float(cleaned)
        except ValueError:
            return 0.0


class EnrichedProduct(BaseModel):
    """Product after enrichment with brand, weight, SEO content."""
    sku: str
    name: str
    name_original: str
    stock: int
    price: Decimal
    cost: Decimal
    minimum: int
    
    category: str
    category_original: str
    brand: Optional[str] = None
    weight_kg: Optional[float] = None
    
    short_description: str
    description: str
    tags: List[str] = Field(default_factory=list)
    
    # WooCommerce specific
    published: bool = True
    manage_stock: bool = True
    
    @computed_field
    @property
    def hash_full(self) -> str:
        """Hash of ALL fields - triggers full update if changed."""
        content = f"{self.sku}|{self.name}|{self.description}|{self.short_description}|{self.category}|{self.brand}|{self.weight_kg}|{','.join(self.tags)}"
        return md5(content.encode()).hexdigest()
    
    @computed_field
    @property
    def hash_fast(self) -> str:
        """Hash of price+stock only - triggers fast update if only these change."""
        content = f"{self.sku}|{self.price}|{self.stock}"
        return md5(content.encode()).hexdigest()
    
    @computed_field
    @property
    def margin_percent(self) -> float:
        """Calculate margin percentage."""
        if self.cost == 0:
            return 0.0
        return float((self.price - self.cost) / self.cost * 100)


class WooPayloadFull(BaseModel):
    """Full WooCommerce product payload for POST/PUT."""
    sku: str
    name: str
    regular_price: str
    stock_quantity: int
    manage_stock: bool = True
    description: str
    short_description: str
    categories: List[dict] = Field(default_factory=list)
    tags: List[dict] = Field(default_factory=list)
    attributes: List[dict] = Field(default_factory=list)
    weight: Optional[str] = None
    status: str = "publish"
    catalog_visibility: str = "visible"
    
    # Meta fields
    meta_data: List[dict] = Field(default_factory=list)
    
    @classmethod
    def from_enriched(cls, product: EnrichedProduct) -> "WooPayloadFull":
        """Create payload from enriched product."""
        payload = cls(
            sku=product.sku,
            name=product.name,
            regular_price=str(product.price),
            stock_quantity=product.stock,
            description=product.description,
            short_description=product.short_description,
            categories=[{"name": product.category}],
            tags=[{"name": tag} for tag in product.tags],
            weight=str(product.weight_kg) if product.weight_kg else None,
            status="publish" if product.published and product.stock > 0 else "draft",
        )
        
        # Add brand as attribute
        if product.brand:
            payload.attributes.append({
                "name": "Marca",
                "options": [product.brand],
                "visible": True,
            })
        
        # Add meta data
        payload.meta_data = [
            {"key": "_custo", "value": str(product.cost)},
            {"key": "_estoque_minimo", "value": str(product.minimum)},
            {"key": "_margem", "value": f"{product.margin_percent:.2f}"},
            {"key": "_categoria_original", "value": product.category_original},
            {"key": "_nome_original", "value": product.name_original},
            {"key": "_marca", "value": product.brand or ""},
        ]
        
        return payload


class WooPayloadFast(BaseModel):
    """Minimal payload for price/stock-only updates."""
    regular_price: str
    stock_quantity: int
    
    @classmethod
    def from_enriched(cls, product: EnrichedProduct) -> "WooPayloadFast":
        """Create fast payload from enriched product."""
        return cls(
            regular_price=str(product.price),
            stock_quantity=product.stock,
        )


class PriceWarning(BaseModel):
    """Warning for blocked price updates."""
    sku: str
    name: str = ""
    old_price: float
    new_price: float
    variation_percent: float
    blocked: bool = True


class ProductChange(BaseModel):
    """Tracks a single product change for detailed reporting."""
    sku: str
    name: str
    change_type: str  # 'new', 'updated', 'blocked'
    old_price: Optional[float] = None
    new_price: float
    old_stock: Optional[int] = None
    new_stock: int
    price_variation: float = 0.0  # Percentage change
    
    @property
    def price_direction(self) -> str:
        """Return emoji based on price direction."""
        if self.old_price is None:
            return "🆕"  # New product
        if self.new_price > self.old_price:
            return "📈"  # Price increased
        elif self.new_price < self.old_price:
            return "📉"  # Price decreased
        return "➖"  # No change


class SyncSummary(BaseModel):
    """Summary of sync operation for notifications."""
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
    
    total_parsed: int = 0
    total_enriched: int = 0
    
    new_products: int = 0
    full_updates: int = 0
    fast_updates: int = 0
    skipped: int = 0
    
    price_warnings: List[PriceWarning] = Field(default_factory=list)
    ghost_skus_zeroed: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    # Detailed tracking for Bot 2.0
    product_changes: List[ProductChange] = Field(default_factory=list)
    
    @property
    def total_synced(self) -> int:
        """Total products actually synced to WooCommerce."""
        return self.new_products + self.full_updates + self.fast_updates
    
    @property
    def top_price_increases(self) -> List[ProductChange]:
        """Top 5 products with biggest price increases."""
        increases = [c for c in self.product_changes if c.price_variation > 0]
        return sorted(increases, key=lambda x: x.price_variation, reverse=True)[:5]
    
    @property
    def top_price_decreases(self) -> List[ProductChange]:
        """Top 5 products with biggest price decreases."""
        decreases = [c for c in self.product_changes if c.price_variation < 0]
        return sorted(decreases, key=lambda x: x.price_variation)[:5]
    
    def to_json_file(self, filepath: str):
        """Save summary to JSON file for bot commands."""
        import json
        data = {
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "total_parsed": self.total_parsed,
            "total_enriched": self.total_enriched,
            "new_products": self.new_products,
            "full_updates": self.full_updates,
            "fast_updates": self.fast_updates,
            "skipped": self.skipped,
            "total_synced": self.total_synced,
            "product_changes": [
                {
                    "sku": c.sku,
                    "name": c.name,
                    "change_type": c.change_type,
                    "old_price": c.old_price,
                    "new_price": c.new_price,
                    "old_stock": c.old_stock,
                    "new_stock": c.new_stock,
                    "price_variation": c.price_variation,
                }
                for c in self.product_changes
            ],
            "price_warnings": [
                {
                    "sku": w.sku,
                    "name": w.name,
                    "old_price": w.old_price,
                    "new_price": w.new_price,
                    "variation_percent": w.variation_percent,
                }
                for w in self.price_warnings
            ],
            "ghost_skus_zeroed": self.ghost_skus_zeroed,
            "errors": self.errors,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


class ProductDBRecord(BaseModel):
    """Database record for product sync state."""
    sku: str
    woo_id: Optional[int] = None
    last_hash_full: Optional[str] = None
    last_hash_fast: Optional[str] = None
    last_price: Optional[float] = None
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
