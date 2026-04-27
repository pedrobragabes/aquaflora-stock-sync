"""
AquaFlora Stock Sync - Product Enricher
Enriches products with brand detection, weight extraction, SEO content.
Ported from processador-estoque-v4.1.js
"""

import logging
import re
from decimal import Decimal
from typing import List, Optional

from .models import RawProduct, EnrichedProduct

logger = logging.getLogger(__name__)


# =============================================================================
# BRAND DATABASE - Ported from JS marcasConhecidas
# =============================================================================
KNOWN_BRANDS = {
    # Pet - Rações Premium
    'royal canin': 'Royal Canin',
    'royalcanin': 'Royal Canin',
    'premier': 'Premier',
    'premier pet': 'Premier Pet',
    'golden': 'Golden',
    'golden formula': 'Golden Formula',
    'farmina': 'Farmina',
    'farmina n&d': 'Farmina N&D',
    'origen': 'Origen',
    'acana': 'Acana',
    'taste of the wild': 'Taste of the Wild',
    'hills': "Hill's",
    'purina': 'Purina',
    'proplan': 'Pro Plan',
    'pro plan': 'Pro Plan',
    
    # Pet - Rações Populares
    'pedigree': 'Pedigree',
    'whiskas': 'Whiskas',
    'friskies': 'Friskies',
    'dog chow': 'Dog Chow',
    'cat chow': 'Cat Chow',
    'special dog': 'Special Dog',
    'special cat': 'Special Cat',
    'luck dog': 'Luck Dog',
    'luck cat': 'Luck Cat',
    'max': 'Max',
    'max cat': 'Max Cat',
    'max dog': 'Max Dog',
    'total': 'Total',
    'total dog': 'Total Dog',
    'total cat': 'Total Cat',
    'sabor': 'Sabor & Vida',
    'sabor e vida': 'Sabor & Vida',
    'sabor vida': 'Sabor & Vida',
    'guabi': 'Guabi',
    'guabi natural': 'Guabi Natural',
    'equilibrio': 'Equilíbrio',
    'naturalis': 'Naturalis',
    
    # Veterinária e Medicamentos
    'nexgard': 'NexGard',
    'bravecto': 'Bravecto',
    'simparic': 'Simparic',
    'revolution': 'Revolution',
    'advocate': 'Advocate',
    'frontline': 'Frontline',
    'seresto': 'Seresto',
    'heartgard': 'Heartgard',
    'drontal': 'Drontal',
    'vermifugo': 'Vermífugo',
    'antipulgas': 'Antipulgas',
    'zoetis': 'Zoetis',
    'virbac': 'Virbac',
    'agener': 'Agener',
    'ceva': 'Ceva',
    'merial': 'Merial',
    
    # Higiene e Beleza Pet
    'petbrilho': 'Pet Brilho',
    'pet society': 'Pet Society',
    'plush': 'Plush',
    'nasus': 'Nasus',
    'kelldrin': 'Kelldrin',
    'vitor': 'Vitor',
    'vitalab': 'Vitalab',
    'biovet': 'Biovet',
    'vetnil': 'Vetnil',
    'ecopet': 'Ecopet',
    
    # Aquarismo
    'alcon': 'Alcon',
    'tetra': 'Tetra',
    'sera': 'Sera',
    'tropical': 'Tropical',
    'nutrafin': 'Nutrafin',
    'ocean tech': 'Ocean Tech',
    'oceantech': 'Ocean Tech',
    'boyu': 'Boyu',
    'sarlo': 'Sarlo',
    'sarlo better': 'Sarlo Better',
    'atman': 'Atman',
    'aquatech': 'Aquatech',
    'resun': 'Resun',
    
    # Aves e Pássaros
    'megazoo': 'Megazoo',
    'alimento': 'Alimento',
    'nutrópica': 'Nutrópica',
    'nutropica': 'Nutrópica',
    'zootekna': 'Zootekna',
    'poytara': 'Poytara',
    'trinca ferro': 'Trinca Ferro',
    
    # Piscina
    'genco': 'Genco',
    'hidroazul': 'Hidroazul',
    'bel gard': 'Bel Gard',
    'belguard': 'Bel Gard',
    'barranets': 'Barranets',
    'hth': 'HTH',
    'acquazero': 'Acquazero',
    
    # Ferramentas e Cutelaria
    'tramontina': 'Tramontina',
    'vonder': 'Vonder',
    'western': 'Western',
    'nautika': 'Nautika',
    'coleman': 'Coleman',
    'guepardo': 'Guepardo',
    'mor': 'Mor',
    'invictus': 'Invictus',
    
    # Pesca
    'marine sports': 'Marine Sports',
    'maruri': 'Maruri',
    'daiwa': 'Daiwa',
    'shimano': 'Shimano',
    'albatroz': 'Albatroz',
    'saint': 'Saint',
    'sumax': 'Sumax',
    
    # Agro e Insumos
    'forth': 'Forth',
    'dimy': 'Dimy',
    'nutriplan': 'Nutriplan',
    'biofertil': 'Biofertil',
    'bionatural': 'BioNatural',
    'vitaplan': 'Vitaplan',
    'plantafol': 'Plantafol',
    
    # Tabacaria
    'palheiro': 'Palheiro',
    'smoking': 'Smoking',
    'zig zag': 'Zig Zag',
    'zigzag': 'Zig Zag',
    'raw': 'RAW',
    'club modiano': 'Club Modiano',
    'copag': 'Copag',
}


# =============================================================================
# NAME CORRECTIONS - Ported from JS aplicarCorrecoesEspecificas
# =============================================================================
NAME_CORRECTIONS = {
    # Animais
    'caes': 'Cães', 'gatos': 'Gatos', 'gato': 'Gato', 'cao': 'Cão',
    'filhotes': 'Filhotes', 'filhote': 'Filhote',
    'adulto': 'Adulto', 'adultos': 'Adultos',
    'senior': 'Senior', 'puppy': 'Puppy', 'junior': 'Junior',
    
    # Abreviações
    'cast': 'Castrado', 'castr': 'Castrado',
    'rp': 'Raça Pequena', 'rm': 'Raça Média', 'rg': 'Raça Grande',
    'rmg': 'Raças Médias e Grandes',
    'ad': 'Adulto', 'fil': 'Filhote',
    'ped': 'Pedaços', 'sach': 'Sachê', 'sache': 'Sachê',
    'lat': 'Lata', 'amb': 'Ambientes',
    'trad': 'Tradicional', 'orig': 'Original',
    'sel': 'Seleção', 'esp': 'Especial',
    'prem': 'Premium', 'nat': 'Natural',
    'jard': 'Jardim', 'fl': 'Flor', 'fr': 'Frutas',
    'veg': 'Vegetais', 'sab': 'Sabor',
    'pt': 'Pote', 'un': 'Unidade', 'cx': 'Caixa',
    'pc': 'Peça', 'pct': 'Pacote',
    'fgo': 'Frango', 'car': 'Carne',
    
    # Acentuação
    'racao': 'Ração', 'racoes': 'Rações',
    'racas': 'Raças', 'raca': 'Raça',
    'medio': 'Médio', 'media': 'Média',
    'graudo': 'Graúdo', 'graúdos': 'Graúdos',
    'pathe': 'Patê', 'pate': 'Patê',
    'umido': 'Úmido', 'agua': 'Água',
    'passaros': 'Pássaros', 'passaro': 'Pássaro',
    'reptil': 'Réptil', 'repteis': 'Répteis',
    
    # Sabores
    'frango': 'Frango', 'carne': 'Carne',
    'peixe': 'Peixe', 'salmao': 'Salmão',
    'vegetais': 'Vegetais', 'arroz': 'Arroz',
    
    # Características
    'castrado': 'Castrado', 'castrados': 'Castrados',
    'light': 'Light', 'premium': 'Premium', 'gold': 'Gold',
    'mini': 'Mini', 'pequenas': 'Pequenas',
    'medias': 'Médias', 'grandes': 'Grandes',
    
    # Unidades
    'kg': 'Kg', 'ml': 'ml', 'cm': 'cm',
}


# =============================================================================
# WEIGHT PATTERNS - Ported from JS extrairPeso
# =============================================================================
WEIGHT_PATTERNS = [
    (r'(\d+(?:[,\.]\d+)?)\s*kg', 1.0),        # 10kg, 10.5kg, 10,5kg
    (r'(\d+(?:[,\.]\d+)?)\s*k(?![a-z])', 1.0),  # 10k
    (r'(\d+)\s*quilos?', 1.0),                  # 10 quilo, 10 quilos
    (r'(\d+(?:[,\.]\d+)?)\s*g(?![a-z])', 0.001),  # 500g (not "golden")
    (r'(\d+(?:[,\.]\d+)?)\s*gramas?', 0.001),     # 500 grama
    (r'(\d+(?:[,\.]\d+)?)\s*ml', 0.001),          # 500ml
    (r'(\d+(?:[,\.]\d+)?)\s*litros?', 1.0),       # 2 litro
    (r'(\d+(?:[,\.]\d+)?)\s*l(?![a-z])', 1.0),    # 2L
]


class ProductEnricher:
    """
    Enriches raw products with brand, weight, category, and SEO content.
    Ported from processador-estoque-v4.1.js
    """
    
    def __init__(self):
        # Compile brand patterns for faster matching
        self._brand_patterns = {
            key: (re.compile(rf'\b{re.escape(key)}\b', re.IGNORECASE), value)
            for key, value in KNOWN_BRANDS.items()
        }
        
        # Compile weight patterns
        self._weight_patterns = [
            (re.compile(pattern, re.IGNORECASE), multiplier)
            for pattern, multiplier in WEIGHT_PATTERNS
        ]
    
    def enrich(self, raw: RawProduct) -> EnrichedProduct:
        """
        Enrich a raw product with brand, weight, SEO content.
        
        Args:
            raw: RawProduct from parser
            
        Returns:
            EnrichedProduct with all enrichments
        """
        # Format name
        formatted_name = self._format_name(raw.name)
        
        # Detect brand - PRIORIDADE: usar marca do CSV, senão detectar
        brand = None
        if raw.brand and raw.brand.upper() not in ('', 'DIVERSAS', 'SEM MARCA', 'N/A'):
            # Usar marca do CSV, formatada corretamente
            brand = self._format_brand_name(raw.brand)
        
        if not brand:
            # Tentar detectar no nome
            brand = self._detect_brand(raw.name)
        
        # INCLUIR MARCA NO TÍTULO se não estiver
        if brand and brand.upper() not in formatted_name.upper():
            formatted_name = f"{formatted_name} - {brand}"
        
        # Extract weight (advanced)
        weight_total, weight_unit, weight_qty = self._extract_weight_details(raw.name)
        weight = weight_total
        
        # Format category
        category = self._format_category(raw.department)
        
        # Generate tags
        tags = self._generate_tags(formatted_name, category, brand)
        
        # Generate descriptions
        short_desc = self._generate_short_description(formatted_name, category, brand)
        long_desc = self._generate_html_description(
            formatted_name, category, brand, weight_total, weight_unit, weight_qty
        )
        
        # Round stock toward nearest integer (KG products like "15,338" lose
        # the fractional kg here — WooCommerce manages stock as integers).
        stock_int = int(round(raw.stock))

        return EnrichedProduct(
            sku=raw.sku,
            ean=raw.ean,
            name=formatted_name,
            name_original=raw.name,
            stock=stock_int,
            price=Decimal(str(round(raw.price, 2))),
            cost=Decimal(str(round(raw.cost, 2))),
            minimum=int(round(raw.minimum)),
            category=category,
            category_original=raw.department,
            brand=brand,
            weight_kg=weight,
            weight_unit_kg=weight_unit,
            weight_total_kg=weight_total,
            weight_qty=weight_qty,
            short_description=short_desc,
            description=long_desc,
            tags=tags,
            published=raw.stock > 0,
        )
    
    def _format_brand_name(self, brand: str) -> str:
        """Format brand name from CSV to proper case."""
        if not brand:
            return ""
        
        # Se já conhecemos essa marca, usar o nome correto
        brand_lower = brand.lower().strip()
        if brand_lower in KNOWN_BRANDS:
            return KNOWN_BRANDS[brand_lower]
        
        # Senão, formatar em Title Case
        return brand.strip().title()
    
    def _detect_brand(self, name: str) -> Optional[str]:
        """Detect brand from product name using pattern matching."""
        name_lower = name.lower()
        
        for key, (pattern, brand_name) in self._brand_patterns.items():
            if pattern.search(name_lower):
                logger.debug(f"Detected brand '{brand_name}' in '{name}'")
                return brand_name
        
        return None
    
    def _extract_weight(self, name: str) -> Optional[float]:
        """Extract total weight from product name, convert to kg."""
        weight_total, _, _ = self._extract_weight_details(name)
        return weight_total

    def _extract_weight_details(self, name: str) -> tuple[Optional[float], Optional[float], Optional[int]]:
        """
        Extract total weight, unit weight and quantity from product name.

        Supports:
        - "2x10kg" (qty=2, unit=10, total=20)
        - "15kg c/2" (qty=2, unit=15, total=30)
        - "10kg + 2kg" (qty=2, total=12)
        """
        if not name:
            return None, None, None

        text = name.lower()

        # 1) Pattern: 2x10kg
        match = re.search(r'(\d+)\s*[xX]\s*(\d+(?:[\.,]\d+)?)\s*kg', text, re.IGNORECASE)
        if match:
            qty = int(match.group(1))
            unit = float(match.group(2).replace(',', '.'))
            total = round(qty * unit, 3)
            return total, round(unit, 3), qty

        # 2) Pattern: 15kg c/2 (com 2)
        match = re.search(r'(\d+(?:[\.,]\d+)?)\s*kg\s*(?:c\/?|c\.|com)\s*(\d+)', text, re.IGNORECASE)
        if match:
            unit = float(match.group(1).replace(',', '.'))
            qty = int(match.group(2))
            total = round(qty * unit, 3)
            return total, round(unit, 3), qty

        # 3) Pattern: 10kg + 2kg
        if '+' in text:
            kg_matches = re.findall(r'(\d+(?:[\.,]\d+)?)\s*kg', text, re.IGNORECASE)
            if len(kg_matches) >= 2:
                values = [float(v.replace(',', '.')) for v in kg_matches]
                total = round(sum(values), 3)
                unit = round(values[0], 3)
                return total, unit, len(values)

        # 4) Fallback: first weight occurrence (kg/g/ml/l)
        for pattern, multiplier in self._weight_patterns:
            match = pattern.search(name)
            if match:
                value_str = match.group(1).replace(",", ".")
                try:
                    value = float(value_str) * multiplier
                    # Sanity check: between 0.001kg and 50kg
                    if 0.001 <= value <= 50:
                        logger.debug(f"Extracted weight {value}kg from '{name}'")
                        return round(value, 3), round(value, 3), 1
                except ValueError:
                    continue

        return None, None, None
    
    def _format_name(self, name: str) -> str:
        """Format product name with title case and corrections."""
        if not name:
            return ""
        
        # Remove extra quotes and spaces
        name = name.strip().strip('"').strip("'")
        
        # Convert to title case
        name = name.lower().title()
        
        # Apply specific corrections
        for wrong, correct in NAME_CORRECTIONS.items():
            pattern = re.compile(rf'\b{re.escape(wrong)}\b', re.IGNORECASE)
            name = pattern.sub(correct, name)
        
        # Remove invalid characters
        name = re.sub(r'[^\w\s\-.,()\&/áàâãéèêíïóôõöúçñÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑº°ª%]', '', name)
        
        # Remove duplicated weight tokens (e.g., "15Kg 15Kg")
        name = re.sub(
            r'\b(\d+(?:[\.,]\d+)?\s*(?:Kg|G|Ml|L))\b(?:\s+\1\b)+',
            r'\1',
            name,
            flags=re.IGNORECASE
        )

        # Truncate if too long
        if len(name) > 100:
            name = name[:97] + "..."
        
        return name
    
    def _format_category(self, category: str) -> str:
        """Format category name."""
        if not category:
            return "Geral"
        
        # Remove version suffixes
        category = re.sub(r'_v?\d+$', '', category, flags=re.IGNORECASE)
        
        # Title case
        return category.strip().lower().title()
    
    def _generate_tags(
        self, name: str, category: str, brand: Optional[str]
    ) -> List[str]:
        """Generate tags for the product."""
        tags = [category]
        
        if brand:
            tags.append(brand)
        
        # Add keyword-based tags
        keywords = ['Premium', 'Gold', 'Special', 'Royal', 'Bio', 'Natural', 
                    'Filhote', 'Adulto', 'Senior']
        for keyword in keywords:
            if keyword.lower() in name.lower():
                tags.append(keyword)
        
        return list(set(tags))  # Remove duplicates
    
    def _generate_short_description(
        self, name: str, category: str, brand: Optional[str]
    ) -> str:
        """Generate short description for SEO."""
        desc = name
        if brand:
            desc += f" | Marca: {brand}"
        desc += f" | Categoria: {category} | AquaFlora Agroshop"
        return desc
    
    def _generate_html_description(
        self, 
        name: str, 
        category: str, 
        brand: Optional[str],
        weight_total: Optional[float],
        weight_unit: Optional[float],
        weight_qty: Optional[int]
    ) -> str:
        """Generate HTML description for WooCommerce with category-specific SEO."""
        
        # Category-specific templates
        category_seo = self._get_category_seo_template(category.lower())
        
        lines = [f'<div class="product-description">']
        lines.append(f'<h2>{name}</h2>')
        
        # Intro paragraph (category-specific)
        if brand:
            intro = f'<p>Produto <strong>{brand}</strong> '
        else:
            intro = '<p>Produto de alta qualidade '
        
        intro += category_seo['intro']
        
        if weight_total:
            weight_formatted = f"{weight_total:.3f}".replace(".", ",")
            intro += f' Com <strong>{weight_formatted}kg</strong>.'
        
        intro += '</p>'
        lines.append(intro)
        
        # Benefits list (category-specific)
        lines.append('<ul class="product-features">')
        
        if brand:
            lines.append(f'  <li>🏷️ <strong>Marca:</strong> {brand}</li>')
        
        if weight_total:
            weight_formatted = f"{weight_total:.3f}".replace(".", ",")
            if weight_qty and weight_unit and weight_qty > 1:
                unit_formatted = f"{weight_unit:.3f}".replace(".", ",")
                lines.append(
                    f'  <li>⚖️ <strong>Peso/Conteúdo:</strong> {weight_qty}x {unit_formatted} Kg '
                    f'(total {weight_formatted} Kg)</li>'
                )
            else:
                lines.append(f'  <li>⚖️ <strong>Peso/Conteúdo:</strong> {weight_formatted} Kg</li>')
        
        lines.append(f'  <li>📦 <strong>Categoria:</strong> {category}</li>')
        
        # Add category-specific benefits
        for benefit in category_seo['benefits']:
            lines.append(f'  <li>{benefit}</li>')
        
        lines.append('</ul>')
        
        # Category-specific CTA
        lines.append('<div class="cta-section">')
        lines.append(f'<p>{category_seo["cta"]}</p>')
        lines.append('<p>⭐ <strong>AquaFlora Agroshop</strong> - Sua loja de confiança!</p>')
        lines.append('</div>')
        lines.append('</div>')
        
        return '\n'.join(lines)
    
    def _get_category_seo_template(self, category: str) -> dict:
        """Get SEO template for specific category."""
        
        # Pet Rações
        if any(k in category for k in ['racao', 'ração', 'pet', 'dog', 'cat', 'cao', 'cão', 'gato']):
            return {
                'intro': 'para garantir a saúde e bem-estar do seu pet. Formulação balanceada com nutrientes essenciais.',
                'benefits': [
                    '🐕 <strong>Saúde completa</strong> para seu pet',
                    '🥗 <strong>Nutrientes balanceados</strong> para cada fase da vida',
                    '✅ <strong>Produto Original</strong> com garantia',
                    '🚚 <strong>Entrega Rápida</strong> para todo o Brasil',
                ],
                'cta': '📞 <strong>Dúvidas sobre o produto?</strong> Nossa equipe de especialistas em nutrição pet está pronta para ajudar!',
            }
        
        # Veterinária / Medicamentos
        if any(k in category for k in ['veterinari', 'medicamento', 'remedio', 'pulga', 'carrapato']):
            return {
                'intro': 'de uso veterinário para proteção e cuidado do seu animal. Eficácia comprovada.',
                'benefits': [
                    '🛡️ <strong>Proteção eficaz</strong> contra parasitas',
                    '💊 <strong>Fórmula veterinária</strong> aprovada',
                    '✅ <strong>Produto Original</strong> lacrado',
                    '📋 <strong>Orientação de uso</strong> na embalagem',
                ],
                'cta': '⚕️ <strong>Importante:</strong> Consulte um veterinário para orientação de dosagem adequada!',
            }
        
        # Aquarismo
        if any(k in category for k in ['aquario', 'aquarismo', 'peixe', 'aquatica']):
            return {
                'intro': 'para o cuidado do seu aquário. Mantenha seus peixes saudáveis e a água cristalina.',
                'benefits': [
                    '🐟 <strong>Ideal para aquários</strong> de água doce e salgada',
                    '💧 <strong>Mantém a qualidade</strong> da água',
                    '✅ <strong>Produto Original</strong> de qualidade',
                    '🚚 <strong>Entrega cuidadosa</strong> para todo o Brasil',
                ],
                'cta': '🐠 <strong>Dúvidas sobre aquarismo?</strong> Temos especialistas prontos para orientar!',
            }
        
        # Pesca
        if any(k in category for k in ['pesca', 'isca', 'anzol', 'vara']):
            return {
                'intro': 'para pescadores exigentes. Equipamento de qualidade para suas melhores pescarias.',
                'benefits': [
                    '🎣 <strong>Qualidade profissional</strong> para pescaria',
                    '💪 <strong>Material resistente</strong> e durável',
                    '✅ <strong>Produto Original</strong> com garantia',
                    '🚚 <strong>Entrega Rápida</strong> para todo o Brasil',
                ],
                'cta': '🎣 <strong>Boa pescaria!</strong> Conte com os melhores equipamentos!',
            }
        
        # Jardim / Agrícola
        if any(k in category for k in ['jardim', 'agricola', 'planta', 'adubo', 'semente']):
            return {
                'intro': 'para o cuidado do seu jardim e plantas. Resultados visíveis em pouco tempo.',
                'benefits': [
                    '🌱 <strong>Favorece o crescimento</strong> saudável',
                    '🌿 <strong>Fórmula desenvolvida</strong> por especialistas',
                    '✅ <strong>Produto Original</strong> de qualidade',
                    '🚚 <strong>Entrega segura</strong> para todo o Brasil',
                ],
                'cta': '🌻 <strong>Jardim mais bonito!</strong> Transforme seu espaço verde!',
            }
        
        # Default template
        return {
            'intro': 'da linha premium. Qualidade AquaFlora Agroshop.',
            'benefits': [
                '✅ <strong>Produto Original</strong> com garantia',
                '🚚 <strong>Entrega Rápida</strong> para todo o Brasil',
                '💳 <strong>Diversas formas de pagamento</strong>',
            ],
            'cta': '📞 <strong>Dúvidas?</strong> Nossa equipe está pronta para ajudar!',
        }

