"""
AquaFlora Stock Sync - Image Scraper Module
Search and download product images using Google Custom Search (primary) 
with DuckDuckGo/Bing as fallback.
Includes Vision AI integration for image quality validation.
"""

from __future__ import annotations

import base64
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple, Dict, TYPE_CHECKING, Any

import requests

# Optional dependencies with proper type handling
HAS_DDGS = False
HAS_PILLOW = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    pass

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    pass

# Type hints for optional modules
if TYPE_CHECKING:
    from duckduckgo_search import DDGS as DDGSType
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Load .env if not already loaded
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

# Google Custom Search API (primary - most reliable)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

# Vision AI Configuration
VISION_AI_ENABLED = os.getenv("VISION_AI_ENABLED", "true").lower() == "true"
VISION_MIN_CONFIDENCE = float(os.getenv("VISION_MIN_CONFIDENCE", "0.6"))

# Default configuration values
MIN_IMAGE_SIZE = 400  # Reduced from 600 to allow more flexibility
MAX_DIMENSION = 1200  # Maximum dimension (will resize if larger)
JPEG_QUALITY = 85
TIMEOUT_SECONDS = 15
SLEEP_MIN = 0.3
SLEEP_MAX = 1.0
MAX_FILE_SIZE_KB = 5  # Minimum file size to be valid

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ImageCandidate:
    """Represents an image candidate found during search."""
    url: str
    thumbnail: str
    title: str
    source: str
    width: int = 0
    height: int = 0
    # Vision AI analysis results
    vision_score: float = 0.0  # Overall quality score (0-1)
    vision_labels: List[str] = field(default_factory=list)  # Detected labels
    is_product_image: bool = False  # Whether Vision AI thinks it's a product
    has_text: bool = False  # Whether image contains text/logo
    safe_search_ok: bool = True  # Whether image passed safe search


@dataclass
class VisionAnalysisResult:
    """Result from Vision AI analysis."""
    is_valid: bool
    score: float  # 0-1 confidence score
    labels: List[str]
    is_product_image: bool
    has_text: bool
    has_logo: bool
    safe_search_ok: bool
    dominant_colors: List[str]
    error: Optional[str] = None


# =============================================================================
# TEXT PROCESSING (Reused from legacy scraper)
# =============================================================================

def clean_product_name(name: str) -> str:
    """
    Clean product name for search queries.
    Removes promotional text, special characters, and normalizes whitespace.
    
    Reused from: Scraping Images Old/src/scraper.py
    """
    if not name:
        return ""
    
    # Stopwords to remove (promotional text)
    stopwords = [
        r"\b(promoção|promocao|oferta|off|desconto|frete grátis|frete gratis)\b",
        r"\b(novo|lançamento|lancamento)\b",
        r"\b(\d+%\s*off)\b",
        r"[!@#$*]",
    ]
    
    s = name.lower()
    for pat in stopwords:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)
    
    return re.sub(r"\s+", " ", s).strip()


def is_bad_image_url(url: str) -> bool:
    """
    Check if URL is likely a bad image (placeholder, logo, etc).
    
    Reused from: Scraping Images Old/src/scraper.py
    """
    bad_tokens = [
        "sprite", "icon", "logo", "placeholder", "blank",
        "spinner", "loading", "1x1", "pixel", "favicon", "avatar",
        "banner", "ad", "advertisement", "tracking", "analytics"
    ]
    u = url.lower()
    return any(tok in u for tok in bad_tokens)


# =============================================================================
# HTTP HELPERS
# =============================================================================

def random_headers() -> dict:
    """Return HTTP headers with random User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }


# =============================================================================
# GOOGLE VISION AI - Image Analysis
# =============================================================================

def analyze_image_with_vision(
    image_content: bytes,
    product_name: str = "",
    category: str = ""
) -> VisionAnalysisResult:
    """
    Analyze image using Google Cloud Vision AI.
    
    Checks:
    - Label detection (is it a product image?)
    - Logo detection (avoid branded/promotional images)
    - Text detection (avoid images with too much text)
    - Safe search (avoid inappropriate content)
    - Image properties (dominant colors)
    
    Cost: ~$1.50 per 1000 images
    
    Returns VisionAnalysisResult with quality score and analysis details.
    """
    if not GOOGLE_API_KEY:
        return VisionAnalysisResult(
            is_valid=True,  # Assume valid if no API key
            score=0.5,
            labels=[],
            is_product_image=True,
            has_text=False,
            has_logo=False,
            safe_search_ok=True,
            dominant_colors=[],
            error="No API key configured"
        )
    
    if not VISION_AI_ENABLED:
        return VisionAnalysisResult(
            is_valid=True,
            score=0.5,
            labels=[],
            is_product_image=True,
            has_text=False,
            has_logo=False,
            safe_search_ok=True,
            dominant_colors=[],
            error="Vision AI disabled"
        )
    
    try:
        # Encode image to base64
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Vision API endpoint
        url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_API_KEY}"
        
        # Request payload with multiple features
        payload = {
            "requests": [{
                "image": {"content": image_base64},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 15},
                    {"type": "LOGO_DETECTION", "maxResults": 5},
                    {"type": "TEXT_DETECTION", "maxResults": 5},
                    {"type": "SAFE_SEARCH_DETECTION"},
                    {"type": "IMAGE_PROPERTIES"},
                ]
            }]
        }
        
        resp = requests.post(url, json=payload, timeout=30)
        
        if resp.status_code != 200:
            logger.warning(f"Vision AI error: {resp.status_code} - {resp.text[:200]}")
            return VisionAnalysisResult(
                is_valid=True,
                score=0.5,
                labels=[],
                is_product_image=True,
                has_text=False,
                has_logo=False,
                safe_search_ok=True,
                dominant_colors=[],
                error=f"API error: {resp.status_code}"
            )
        
        data = resp.json()
        response = data.get("responses", [{}])[0]
        
        # Parse labels
        labels = []
        label_scores = []
        for label in response.get("labelAnnotations", []):
            labels.append(label.get("description", "").lower())
            label_scores.append(label.get("score", 0))
        
        # Parse logos
        logos = [l.get("description", "") for l in response.get("logoAnnotations", [])]
        has_logo = len(logos) > 0
        
        # Parse text
        texts = response.get("textAnnotations", [])
        has_text = len(texts) > 3  # Allow some text (product name, etc)
        text_content = texts[0].get("description", "") if texts else ""
        
        # Safe search
        safe_search = response.get("safeSearchAnnotation", {})
        safe_search_ok = all(
            safe_search.get(key, "VERY_UNLIKELY") in ["UNKNOWN", "VERY_UNLIKELY", "UNLIKELY"]
            for key in ["adult", "violence", "racy"]
        )
        
        # Dominant colors
        dominant_colors = []
        props = response.get("imagePropertiesAnnotation", {})
        for color in props.get("dominantColors", {}).get("colors", [])[:3]:
            rgb = color.get("color", {})
            dominant_colors.append(f"#{int(rgb.get('red', 0)):02x}{int(rgb.get('green', 0)):02x}{int(rgb.get('blue', 0)):02x}")
        
        # Calculate product score
        is_product_image, product_score = _calculate_product_score(
            labels, 
            product_name, 
            category,
            has_logo,
            has_text,
            text_content
        )
        
        logger.debug(f"Vision AI: score={product_score:.2f}, labels={labels[:5]}, logo={has_logo}, text={has_text}")
        
        return VisionAnalysisResult(
            is_valid=product_score >= VISION_MIN_CONFIDENCE,
            score=product_score,
            labels=labels,
            is_product_image=is_product_image,
            has_text=has_text,
            has_logo=has_logo,
            safe_search_ok=safe_search_ok,
            dominant_colors=dominant_colors,
            error=None
        )
        
    except Exception as e:
        logger.warning(f"Vision AI analysis failed: {e}")
        return VisionAnalysisResult(
            is_valid=True,  # Don't block on errors
            score=0.5,
            labels=[],
            is_product_image=True,
            has_text=False,
            has_logo=False,
            safe_search_ok=True,
            dominant_colors=[],
            error=str(e)
        )


def _calculate_product_score(
    labels: List[str],
    product_name: str,
    category: str,
    has_logo: bool,
    has_text: bool,
    text_content: str
) -> Tuple[bool, float]:
    """
    Calculate how likely this image is a good product photo.
    
    Returns (is_product_image, score)
    """
    score = 0.5  # Start neutral
    
    # =======================================================================
    # SEMANTIC VALIDATION - Labels must match product being searched
    # =======================================================================
    product_lower = product_name.lower() if product_name else ""
    category_lower = category.lower() if category else ""
    
    # Extract keywords from product name for semantic matching
    product_keywords = set(product_lower.split())
    
    # =======================================================================
    # PRODUCT_SEMANTICS - Mapeamento completo baseado no Athos.csv
    # Departamentos: PESCA, PET, FARMACIA, AQUARISMO, PASSAROS, RACAO, 
    #                CUTELARIA, PISCINA, AVES, GERAL, FERRAMENTAS, TABACARIA
    # =======================================================================
    PRODUCT_SEMANTICS = {
        # ===== PESCA (1238 produtos) =====
        "anzol": ["fishing", "hook", "metal", "steel", "tackle"],
        "linha": ["fishing line", "thread", "nylon", "string", "spool"],
        "vara": ["fishing rod", "pole", "rod", "carbon", "fiberglass"],
        "molinete": ["fishing reel", "reel", "spinning", "tackle"],
        "isca": ["lure", "bait", "fishing", "plastic", "artificial"],
        "isca artificial": ["lure", "bait", "fishing", "plastic", "rubber"],
        "girador": ["swivel", "fishing", "tackle", "metal", "connector"],
        "chumbada": ["sinker", "lead", "weight", "fishing", "metal"],
        "carretilha": ["baitcasting", "reel", "fishing", "tackle"],
        "caixa pesca": ["tackle box", "fishing", "container", "plastic"],
        "arremesso": ["casting", "fishing", "rod", "spinning"],
        "alicate": ["pliers", "tool", "fishing", "metal", "grip"],
        "lanterna": ["flashlight", "lamp", "light", "led", "torch"],
        "rede": ["net", "fishing net", "mesh", "nylon"],
        "flutuador": ["float", "bobber", "fishing", "buoy"],
        "chumbo": ["sinker", "lead", "weight", "fishing"],
        "encastoado": ["leader", "wire", "fishing", "steel"],
        "multifilamento": ["braided line", "fishing line", "nylon"],
        "anzol circle": ["circle hook", "fishing", "hook"],
        "jig": ["jig", "lure", "fishing", "metal"],
        "spinner": ["spinner", "lure", "fishing", "metal"],
        
        # ===== PET (971 produtos) =====
        "coleira": ["collar", "pet", "dog", "cat", "leash", "nylon", "leather"],
        "peitoral": ["harness", "pet", "dog", "chest", "strap"],
        "comedouro": ["bowl", "feeder", "pet", "dog", "cat", "food bowl", "dish"],
        "bebedouro": ["water bowl", "dispenser", "pet", "fountain", "bottle"],
        "brinquedo": ["toy", "pet", "dog", "cat", "ball", "plush", "rubber"],
        "mordedor": ["chew toy", "dog", "pet", "rubber", "bone"],
        "shampoo": ["shampoo", "bottle", "pet", "grooming", "liquid", "dog", "cat"],
        "condicionador": ["conditioner", "bottle", "pet", "grooming", "liquid"],
        "escova pet": ["brush", "pet", "grooming", "dog", "cat", "comb"],
        "cama pet": ["bed", "pet", "dog", "cat", "cushion", "sleeping"],
        "casinha": ["house", "pet", "dog", "shelter", "kennel"],
        "transporte": ["carrier", "crate", "pet", "transport", "cage"],
        "tapete": ["mat", "pet", "pad", "absorbent", "training"],
        "fralda": ["diaper", "pet", "dog", "absorbent", "hygiene"],
        "ossinho": ["bone", "treat", "dog", "pet", "snack", "chew"],
        "petisco": ["treat", "snack", "pet", "dog", "cat", "food"],
        "sache": ["pouch", "wet food", "pet", "cat", "dog", "sachet", "dog food", "pet food"],
        "focinheira": ["muzzle", "dog", "pet", "restraint"],
        "guia": ["leash", "lead", "pet", "dog", "walking"],
        "caixa de areia": ["litter box", "cat", "pet", "sandbox"],
        "areia gato": ["cat litter", "sand", "pet", "absorbent"],
        "arranhador": ["scratching post", "cat", "pet", "sisal"],
        "tosa": ["grooming", "clipper", "shaver", "pet"],
        "cortador unha": ["nail clipper", "pet", "grooming", "dog", "cat"],
        
        # ===== RACAO (187 produtos) =====
        "racao": ["pet food", "bag", "packaging", "dog food", "cat food", "animal food", "kibble"],
        "special dog": ["pet food", "bag", "dog food", "packaging", "dog", "puppy"],
        "golden": ["pet food", "bag", "dog food", "premium"],
        "premier": ["pet food", "bag", "dog food", "cat food", "premium"],
        "bionatural": ["pet food", "bag", "natural", "dog food"],
        "whiskas": ["cat food", "pet food", "bag", "pouch"],
        "pedigree": ["dog food", "pet food", "bag", "packaging"],
        "friskies": ["cat food", "pet food", "bag", "packaging"],
        "magnus": ["pet food", "dog food", "bag", "packaging"],
        "premium cat": ["cat food", "pet food", "premium", "bag"],
        "filhote": ["puppy", "pet food", "dog food", "young"],
        "adulto": ["adult", "pet food", "dog food", "cat food"],
        "senior": ["senior", "pet food", "elderly", "dog food"],
        
        # ===== FARMACIA (500 produtos) =====
        "vermifugo": ["medicine", "tablet", "pill", "box", "veterinary", "pet"],
        "antipulga": ["flea", "medicine", "pet", "treatment", "spray", "drop"],
        "vacina": ["vaccine", "medicine", "vial", "syringe", "veterinary"],
        "seringa": ["syringe", "medical", "injection", "plastic"],
        "agulha": ["needle", "medical", "syringe", "steel", "metal"],
        "pomada": ["ointment", "cream", "tube", "medicine", "topical"],
        "spray": ["spray", "bottle", "aerosol", "can", "medicine"],
        "comprimido": ["tablet", "pill", "medicine", "box", "blister"],
        "injetavel": ["injectable", "vial", "medicine", "veterinary"],
        "antibiotico": ["antibiotic", "medicine", "tablet", "bottle"],
        
        # ===== AQUARISMO (271 produtos) =====
        "aquario": ["aquarium", "tank", "glass", "fish", "water"],
        "filtro aqua": ["filter", "aquarium", "pump", "water"],
        "bomba aqua": ["pump", "aquarium", "water", "motor"],
        "substrato": ["substrate", "gravel", "sand", "aquarium", "bottom"],
        "cascalho": ["gravel", "pebbles", "aquarium", "decoration"],
        "termostato": ["heater", "thermostat", "aquarium", "water"],
        "oxigenador": ["air pump", "aerator", "aquarium", "oxygen"],
        "mangueira aqua": ["tubing", "hose", "aquarium", "plastic", "silicone"],
        "alcon": ["fish food", "aquarium", "pet food", "granule", "flake"],
        "betta": ["fish food", "betta", "aquarium", "small fish"],
        
        # ===== PASSAROS (264 produtos) =====
        "gaiola": ["cage", "bird", "wire", "metal", "aviary"],
        "viveiro": ["aviary", "cage", "bird", "large cage"],
        "poleiro": ["perch", "bird", "cage", "wood", "plastic"],
        "comedouro passaro": ["feeder", "bird", "cage", "bowl"],
        "ninho": ["nest", "bird", "breeding", "cage"],
        "farinhada": ["bird food", "mix", "breeding", "supplement"],
        "canario": ["bird food", "canary", "seed", "mix"],
        "coleiro": ["bird food", "seed", "finch", "mix"],
        "curio": ["bird food", "seed", "mix", "premium"],
        "calopsita": ["bird food", "cockatiel", "seed", "mix"],
        "trinca ferro": ["bird food", "seed", "mix", "wild bird"],
        
        # ===== AVES - Criação (22 produtos) =====
        "frango": ["poultry", "chicken", "feeder", "waterer", "farm"],
        "pintinho": ["chick", "poultry", "chicken", "baby"],
        "codorna": ["quail", "poultry", "bird", "farm"],
        "galinha": ["chicken", "hen", "poultry", "farm"],
        
        # ===== PISCINA (31 produtos) =====
        "aspirador piscina": ["pool vacuum", "cleaner", "pool", "cleaning"],
        "escova piscina": ["pool brush", "cleaning", "pool", "bristle"],
        "cloro": ["chlorine", "pool", "chemical", "tablet", "bucket"],
        "peneira piscina": ["skimmer", "net", "pool", "cleaning", "mesh"],
        "mangueira piscina": ["pool hose", "tubing", "flexible", "plastic"],
        "cabo piscina": ["pool pole", "telescopic", "aluminum", "handle"],
        
        # ===== RATICIDAS/VENENOS =====
        "raticida": ["pest control", "poison", "rodent", "rat", "box", "packaging", "pest"],
        "veneno": ["poison", "pest control", "chemical", "bottle", "packaging"],
        "inseticida": ["insecticide", "spray", "pest control", "bottle", "aerosol"],
        "formicida": ["ant killer", "pest control", "poison", "bait"],
        "mata rato": ["rat poison", "pest control", "rodent", "bait"],
        
        # ===== TABACARIA =====
        "isqueiro": ["lighter", "flame", "plastic", "metal", "fire"],
        "cigarro": ["cigarette", "tobacco", "pack", "box", "smoking"],
        "tabaco": ["tobacco", "pouch", "smoking", "pack"],
        "piteira": ["cigarette holder", "filter", "smoking", "plastic"],
        "seda": ["rolling paper", "paper", "smoking", "pack"],
        "cinzeiro": ["ashtray", "bowl", "glass", "ceramic"],
        "cachimbo": ["pipe", "smoking", "wood", "tobacco"],
        "narguilé": ["hookah", "shisha", "water pipe", "smoking"],
        
        # ===== FOGOS/TRAQUES =====
        "traque": ["firecracker", "firework", "pyrotechnics", "explosive", "box"],
        "traques": ["firecracker", "firework", "pyrotechnics", "box"],
        "fogos": ["firework", "pyrotechnics", "explosive", "rocket"],
        "bombinha": ["firecracker", "firework", "cracker", "explosive"],
        "rojao": ["firework", "rocket", "pyrotechnics"],
        "foguete": ["firework", "rocket", "pyrotechnics", "explosive"],
        "espoleta": ["cap", "explosive", "pyrotechnics", "toy"],
        
        # ===== MINERAIS/SUPLEMENTOS ANIMAIS =====
        "dolomita": ["mineral", "calcium", "powder", "supplement", "white", "stone", "rock"],
        "pedra": ["stone", "rock", "mineral", "calcium", "supplement"],
        "calcio": ["calcium", "mineral", "supplement", "white", "powder"],
        "sal mineral": ["mineral salt", "supplement", "block", "lick"],
        "bloco mineral": ["mineral block", "salt lick", "supplement", "animal"],
        
        # ===== CUTELARIA (55 produtos) =====
        "canivete": ["knife", "blade", "pocket knife", "folding", "steel"],
        "faca": ["knife", "blade", "steel", "handle", "cutting"],
        "chaira": ["sharpening steel", "knife", "sharpener", "metal"],
        "bainha": ["sheath", "holster", "leather", "knife case"],
        "tesoura": ["scissors", "shears", "cutting", "blade"],
        "afiador": ["sharpener", "knife", "whetstone", "steel"],
        
        # ===== FERRAMENTAS (122 produtos) =====
        "chave": ["wrench", "tool", "metal", "screwdriver", "socket"],
        "martelo": ["hammer", "tool", "metal", "handle"],
        "alicate ferr": ["pliers", "tool", "metal", "grip", "cutting"],
        "furadeira": ["drill", "power tool", "electric", "motor"],
        "serra": ["saw", "blade", "cutting", "tool"],
        "parafuso": ["screw", "hardware", "metal", "fastener"],
        "prego": ["nail", "hardware", "metal", "fastener"],
        "trena": ["tape measure", "tool", "measuring", "ruler"],
        
        # ===== GERAL - Hardware/Materiais =====
        "abraca": ["cable tie", "zip tie", "nylon", "fastener", "plastic", "strap"],
        "mangueira": ["hose", "tubing", "flexible", "plastic", "rubber"],
        "arame": ["wire", "metal", "steel", "fence"],
        "corda": ["rope", "cord", "string", "nylon", "twine"],
        "corrente": ["chain", "metal", "link", "steel"],
        "lona": ["tarp", "canvas", "cover", "plastic", "waterproof"],
        "balde": ["bucket", "pail", "container", "plastic"],
        "regador": ["watering can", "garden", "plastic", "spout"],
        
        # ===== VESTUÁRIO/EPI =====
        "botina": ["boot", "footwear", "safety", "leather", "work"],
        "macacao": ["coverall", "overalls", "workwear", "uniform"],
        "camiseta": ["t-shirt", "shirt", "clothing", "fabric", "textile"],
        "luva": ["glove", "safety", "protection", "hand", "rubber", "leather"],
        "capacete": ["helmet", "safety", "hard hat", "protection"],
        "oculos": ["glasses", "eyewear", "safety", "protection", "lens"],
    }
    
    # Find which semantic category this product belongs to
    expected_labels = []
    for keyword, semantic_labels in PRODUCT_SEMANTICS.items():
        if keyword in product_lower:
            expected_labels.extend(semantic_labels)
    
    # Also check category/department for context
    CATEGORY_SEMANTICS = {
        "pesca": ["fishing", "tackle", "rod", "reel", "hook", "bait", "outdoor"],
        "pet": ["pet", "dog", "cat", "animal", "collar", "leash", "toy"],
        "racao": ["pet food", "bag", "packaging", "dog food", "cat food"],
        "farmacia": ["medicine", "veterinary", "bottle", "tablet", "medical"],
        "aquarismo": ["aquarium", "fish", "tank", "water", "pump"],
        "passaros": ["bird", "cage", "feeder", "seed", "aviary"],
        "aves": ["poultry", "chicken", "farm", "feeder"],
        "piscina": ["pool", "cleaning", "chlorine", "pump"],
        "cutelaria": ["knife", "blade", "steel", "cutting"],
        "ferramentas": ["tool", "hardware", "metal", "wrench"],
        "tabacaria": ["lighter", "smoking", "tobacco", "cigarette", "pipe", "firework", "firecracker"],
        "geral": ["product", "packaging", "general", "hardware"],
    }
    
    for cat_key, cat_labels in CATEGORY_SEMANTICS.items():
        if cat_key in category_lower:
            expected_labels.extend(cat_labels)
    
    # Remove duplicates
    expected_labels = list(set(expected_labels))
    
    # If we have semantic expectations, validate against them
    if expected_labels:
        # Check if any labels match expected semantics
        matching_labels = sum(1 for label in labels if any(exp in label for exp in expected_labels))
        
        if matching_labels == 0:
            # CRITICAL: Labels don't match what we're looking for
            # This catches cases like abraçadeira returning bottle/cosmetics
            score -= 0.4
            logger.debug(f"Semantic mismatch: expected {expected_labels[:3]}, got {labels[:5]}")
        else:
            score += min(matching_labels * 0.1, 0.2)
    
    # =======================================================================
    # NEGATIVE INDICATORS - Labels that suggest bad images
    # =======================================================================
    negative_labels = [
        "screenshot", "text", "document", "website", "webpage",
        "collage", "meme", "cartoon", "illustration", "drawing",
        "person", "people", "human", "face", "selfie",
        "advertisement", "banner", "poster", "flyer",
        "stock photo", "watermark",
    ]
    
    # Check negative labels
    negative_matches = sum(1 for label in labels if any(n in label for n in negative_labels))
    score -= min(negative_matches * 0.15, 0.4)  # Up to -0.4
    
    # =======================================================================
    # MISMATCH DETECTION - Detect clearly wrong product types
    # =======================================================================
    # If searching for hardware/tools but image shows cosmetics/food
    hardware_keywords = ["abraca", "nylon", "parafuso", "ferramenta", "porca", "arruela"]
    is_hardware = any(kw in product_lower for kw in hardware_keywords)
    
    if is_hardware:
        # Penalize cosmetics/food labels for hardware products
        wrong_labels = ["cosmetics", "personal care", "beauty", "food", "beverage", 
                       "bottle", "lotion", "cream", "perfume", "makeup"]
        wrong_matches = sum(1 for label in labels if any(w in label for w in wrong_labels))
        if wrong_matches > 0:
            score -= 0.3 * wrong_matches
            logger.debug(f"Hardware product showing wrong labels: {labels[:5]}")
    
    # =======================================================================
    # POSITIVE INDICATORS (generic, only if no semantic validation)
    # =======================================================================
    if not expected_labels:
        # Generic positive labels for products
        positive_labels = [
            "product", "packaging", "container", "box", "bag",
        ]
        positive_matches = sum(1 for label in labels if any(p in label for p in positive_labels))
        score += min(positive_matches * 0.05, 0.15)  # Reduced weight
    
    # Bonus if product name appears in detected text
    if product_name and text_content:
        clean_name = clean_product_name(product_name)
        name_words = clean_name.split()[:3]  # First 3 words
        text_lower = text_content.lower()
        matches = sum(1 for w in name_words if len(w) > 3 and w in text_lower)
        if matches >= 2:
            score += 0.2  # Product name detected in image
    
    # Penalty for logos (probably promotional/branded image)
    if has_logo:
        score -= 0.1
    
    # Penalty for too much text (probably infographic/promotional)
    if has_text and len(text_content) > 100:
        score -= 0.15
    
    # Category-specific bonuses
    if category:
        cat_lower = category.lower()
        if any(c in cat_lower for c in ["cerveja", "bebida", "drink"]):
            if any(l in labels for l in ["bottle", "can", "beverage", "drink", "beer"]):
                score += 0.15
        elif any(c in cat_lower for c in ["pet", "ração", "animal"]):
            if any(l in labels for l in ["pet food", "animal", "dog", "cat", "fish"]):
                score += 0.15
    
    # Clamp score
    score = max(0.0, min(1.0, score))
    
    is_product = score >= VISION_MIN_CONFIDENCE
    
    return is_product, score


def validate_image_with_vision(
    url: str,
    product_name: str = "",
    category: str = "",
    download_first: bool = True
) -> Tuple[bool, VisionAnalysisResult, Optional[bytes]]:
    """
    Download and validate an image using Vision AI.
    
    Returns (is_valid, analysis_result, image_content)
    """
    content = None
    
    if download_first:
        content = download_image(url)
        if not content:
            return False, VisionAnalysisResult(
                is_valid=False, score=0, labels=[], is_product_image=False,
                has_text=False, has_logo=False, safe_search_ok=True,
                dominant_colors=[], error="Download failed"
            ), None
        
        # Basic size validation first
        is_valid_size, w, h = validate_image(content)
        if not is_valid_size:
            return False, VisionAnalysisResult(
                is_valid=False, score=0, labels=[], is_product_image=False,
                has_text=False, has_logo=False, safe_search_ok=True,
                dominant_colors=[], error=f"Image too small: {w}x{h}"
            ), None
    
    # Analyze with Vision AI
    if content:
        result = analyze_image_with_vision(content, product_name, category)
        return result.is_valid, result, content
    
    return False, VisionAnalysisResult(
        is_valid=False, score=0, labels=[], is_product_image=False,
        has_text=False, has_logo=False, safe_search_ok=True,
        dominant_colors=[], error="No content"
    ), None


# =============================================================================
# SEARCH ENGINES
# =============================================================================

def search_images_google(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 1  # Default to 1 - first result is usually best
) -> List[ImageCandidate]:
    """
    Search images using Google Custom Search API.
    Primary search engine - most reliable results.
    
    Cost: ~$5 per 1000 queries
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logger.debug("Google API not configured, skipping")
        return []
    
    candidates = []
    clean_name = clean_product_name(product_name)
    
    if not clean_name:
        return []
    
    # Build query - product name + category for better results
    if category and category != "SEM_CATEGORIA":
        query = f"{clean_name} {category}"
    else:
        query = clean_name
    
    try:
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        
        # Google Custom Search API
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "searchType": "image",
            "num": min(max_results * 2, 10),  # Fetch more to filter
            "imgSize": "large",
            "imgType": "photo",
            "safe": "off",
        }
        
        resp = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        
        if resp.status_code == 429:
            logger.warning("Google API rate limit reached")
            return []
        
        if resp.status_code != 200:
            logger.warning(f"Google API error: {resp.status_code}")
            return []
        
        data = resp.json()
        items = data.get("items", [])
        
        for item in items:
            image_url = item.get("link", "")
            
            if not image_url or is_bad_image_url(image_url):
                continue
            
            # Get image metadata
            image_info = item.get("image", {})
            
            candidates.append(ImageCandidate(
                url=image_url,
                thumbnail=item.get("image", {}).get("thumbnailLink", image_url),
                title=item.get("title", ""),
                source="google",
                width=image_info.get("width", 0),
                height=image_info.get("height", 0),
            ))
            
            if len(candidates) >= max_results:
                break
        
        if candidates:
            logger.info(f"Google found {len(candidates)} image(s) for: {query[:50]}")
        
    except Exception as e:
        logger.warning(f"Google search error: {e}")
    
    return candidates

def search_images_duckduckgo(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 6
) -> List[ImageCandidate]:
    """
    Search images using DuckDuckGo.
    
    Strategy (in order of specificity):
    1. Product name + SKU
    2. Product name + category
    3. EAN barcode (if available)
    4. Just product name
    """
    if not HAS_DDGS:
        logger.warning("duckduckgo-search not installed, skipping DuckDuckGo search")
        return []
    
    candidates = []
    queries = []
    
    clean_name = clean_product_name(product_name)
    
    # Build query list in order of preference
    if clean_name and sku:
        queries.append(f"{clean_name} {sku}")
    
    if clean_name and category:
        queries.append(f"{clean_name} {category}")
    
    if ean and len(ean) >= 8:
        queries.append(f'"{ean}"')
    
    if clean_name and len(clean_name) >= 5:
        queries.append(clean_name)
    
    # Try each query until we find results
    for query in queries:
        try:
            time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
            
            with DDGS() as ddgs:  # type: ignore[possibly-undefined]
                results = list(ddgs.images(
                    keywords=query,
                    region="br-pt",
                    safesearch="off",
                    size="Medium",
                    type_image="photo",
                    max_results=max_results * 2  # Fetch more to filter bad ones
                ))
            
            for r in results:
                if not isinstance(r, dict):
                    continue
                
                url = r.get("image", "")
                if not url or is_bad_image_url(url):
                    continue
                
                candidates.append(ImageCandidate(
                    url=url,
                    thumbnail=r.get("thumbnail", url),
                    title=r.get("title", ""),
                    source="duckduckgo",
                    width=int(r.get("width", 0) or 0),
                    height=int(r.get("height", 0) or 0),
                ))
                
                if len(candidates) >= max_results:
                    break
            
            if candidates:
                logger.info(f"DuckDuckGo found {len(candidates)} images for query: {query}")
                break
                
        except Exception as e:
            logger.warning(f"DuckDuckGo search error for '{query}': {e}")
            continue
    
    return candidates[:max_results]


def search_images_bing(
    product_name: str,
    category: str = "",
    max_results: int = 6
) -> List[ImageCandidate]:
    """
    Search images using Bing as fallback.
    Uses HTML scraping since there's no free official API.
    """
    candidates = []
    clean_name = clean_product_name(product_name)
    
    if not clean_name:
        return []
    
    # Build query
    query = clean_name
    if category:
        query = f"{clean_name} {category}"
    
    try:
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        
        # Bing Images search URL
        search_url = "https://www.bing.com/images/search"
        params = {
            "q": query,
            "form": "HDRSC2",
            "first": "1",
            "tsc": "ImageBasicHover",
        }
        
        session = requests.Session()
        session.headers.update(random_headers())
        
        resp = session.get(search_url, params=params, timeout=TIMEOUT_SECONDS)
        
        if resp.status_code != 200:
            logger.warning(f"Bing returned status {resp.status_code}")
            return []
        
        # Extract image URLs via regex (Bing uses murl:"URL" format)
        pattern = r'murl":"(https?://[^"]+)"'
        matches = re.findall(pattern, resp.text)
        
        seen = set()
        for url in matches:
            if url in seen:
                continue
            seen.add(url)
            
            if is_bad_image_url(url):
                continue
            
            # Decode escaped characters
            url = url.replace("\\u002f", "/").replace("\\/", "/")
            
            candidates.append(ImageCandidate(
                url=url,
                thumbnail=url,
                title="",
                source="bing",
                width=0,
                height=0,
            ))
            
            if len(candidates) >= max_results:
                break
        
        if candidates:
            logger.info(f"Bing found {len(candidates)} images for query: {query}")
        
    except Exception as e:
        logger.warning(f"Bing search error for '{query}': {e}")
    
    return candidates


def search_images(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 1  # Default to 1 - first result is usually best
) -> List[ImageCandidate]:
    """
    Main search function with cascade:
    1. Google Custom Search (if API key configured) - most reliable
    2. DuckDuckGo (free, decent quality)
    3. Bing scraping (last resort)
    """
    candidates = []
    
    # 1. Try Google first (if configured)
    if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        candidates = search_images_google(
            product_name=product_name,
            sku=sku,
            ean=ean,
            category=category,
            max_results=max_results
        )
        if candidates:
            return candidates
    
    # 2. Fallback to DuckDuckGo
    candidates = search_images_duckduckgo(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_results=max_results
    )
    
    if candidates:
        return candidates
    
    # 3. Last resort: Bing scraping
    logger.info(f"DuckDuckGo found nothing, trying Bing for SKU {sku}")
    candidates = search_images_bing(
        product_name=product_name,
        category=category,
        max_results=max_results
    )
    
    return candidates


# =============================================================================
# DOWNLOAD & VALIDATION
# =============================================================================

def download_image(url: str, timeout: int = TIMEOUT_SECONDS) -> Optional[bytes]:
    """Download image and return raw bytes."""
    try:
        session = requests.Session()
        session.headers.update(random_headers())
        
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        
        if resp.status_code != 200:
            return None
        
        content_type = resp.headers.get("Content-Type", "").lower()
        
        # Verify it's actually an image
        if "image" not in content_type and "octet-stream" not in content_type:
            if "text/html" in content_type:
                return None
        
        return resp.content
        
    except Exception as e:
        logger.debug(f"Download failed for {url}: {e}")
        return None


def validate_image(
    content: bytes,
    min_size: int = MIN_IMAGE_SIZE
) -> Tuple[bool, int, int]:
    """
    Validate image has minimum resolution.
    Returns (is_valid, width, height).
    """
    if not content or len(content) < MAX_FILE_SIZE_KB * 1024:
        return False, 0, 0
    
    if not HAS_PILLOW:
        # Can't validate without Pillow, assume it's OK
        return True, 0, 0
    
    try:
        img = Image.open(BytesIO(content))  # type: ignore[possibly-undefined]
        w, h = img.size
        
        if w < min_size or h < min_size:
            logger.debug(f"Image too small: {w}x{h} (min: {min_size})")
            return False, w, h
        
        return True, w, h
        
    except Exception as e:
        logger.debug(f"Image validation failed: {e}")
        return False, 0, 0


def process_and_save_image(
    content: bytes,
    sku: str,
    output_dir: Path,
    max_dimension: int = MAX_DIMENSION,
    quality: int = JPEG_QUALITY
) -> Optional[Path]:
    """
    Process image (resize, convert to JPEG) and save to disk.
    Returns path to saved file or None on error.
    """
    if not HAS_PILLOW:
        logger.warning("Pillow not installed - saving without processing")
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{sku}.jpg"
        with open(out_path, "wb") as f:
            f.write(content)
        return out_path
    
    try:
        img = Image.open(BytesIO(content))  # type: ignore[possibly-undefined]
        
        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        w, h = img.size
        
        # Resize if too large
        if max(w, h) > max_dimension:
            ratio = max_dimension / max(w, h)
            img = img.resize(
                (int(w * ratio), int(h * ratio)),
                Image.Resampling.LANCZOS  # type: ignore[possibly-undefined]
            )
            w, h = img.size
        
        # Create square canvas with white background
        max_side = max(w, h)
        background = Image.new("RGB", (max_side, max_side), (255, 255, 255))  # type: ignore[possibly-undefined]
        offset = ((max_side - w) // 2, (max_side - h) // 2)
        background.paste(img, offset)
        
        # Save
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{sku}.jpg"
        background.save(out_path, "JPEG", quality=quality, optimize=True)
        
        logger.info(f"Saved processed image: {out_path}")
        return out_path
        
    except Exception as e:
        logger.error(f"Error processing image for SKU {sku}: {e}")
        return None


def download_and_validate(
    url: str,
    min_size: int = MIN_IMAGE_SIZE
) -> Tuple[Optional[bytes], int, int]:
    """
    Download image and validate resolution.
    Returns (content, width, height) or (None, 0, 0) on failure.
    """
    content = download_image(url)
    if not content:
        return None, 0, 0
    
    is_valid, w, h = validate_image(content, min_size)
    if not is_valid:
        return None, w, h
    
    return content, w, h


# =============================================================================
# HIGH-LEVEL API
# =============================================================================

def search_and_get_thumbnails(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 6
) -> List[dict]:
    """
    Search for images and return list of candidates with metadata.
    Used by the curator service for displaying options to user.
    """
    candidates = search_images(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_results=max_results
    )
    
    return [
        {
            "url": c.url,
            "thumbnail": c.thumbnail,
            "title": c.title,
            "source": c.source,
            "width": c.width,
            "height": c.height,
        }
        for c in candidates
    ]


def search_and_validate_best_image(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_candidates: int = 5,
    use_vision_ai: bool = True
) -> Tuple[Optional[bytes], Optional[ImageCandidate], Optional[VisionAnalysisResult]]:
    """
    Search for images and automatically select the best one using Vision AI.
    
    This function:
    1. Searches for image candidates
    2. Downloads and validates each candidate
    3. Uses Vision AI to score each image
    4. Returns the best scoring image
    
    Args:
        product_name: Name of the product
        sku: Product SKU
        ean: Product EAN barcode
        category: Product category
        max_candidates: Maximum candidates to evaluate
        use_vision_ai: Whether to use Vision AI for validation
    
    Returns:
        (image_content, candidate_info, vision_result) or (None, None, None)
    """
    candidates = search_images(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_results=max_candidates
    )
    
    if not candidates:
        logger.warning(f"No image candidates found for: {product_name}")
        return None, None, None
    
    best_content = None
    best_candidate = None
    best_result = None
    best_score = -1.0
    
    for candidate in candidates:
        logger.debug(f"Evaluating candidate: {candidate.url[:60]}...")
        
        # Download image
        content = download_image(candidate.url)
        if not content:
            continue
        
        # Basic validation
        is_valid, w, h = validate_image(content)
        if not is_valid:
            logger.debug(f"Image too small: {w}x{h}")
            continue
        
        # Vision AI validation (if enabled)
        if use_vision_ai and VISION_AI_ENABLED and GOOGLE_API_KEY:
            result = analyze_image_with_vision(content, product_name, category)
            
            if not result.safe_search_ok:
                logger.warning(f"Image failed safe search: {candidate.url[:50]}")
                continue
            
            if result.score > best_score:
                best_score = result.score
                best_content = content
                best_candidate = candidate
                best_result = result
                
                # Update candidate with Vision AI data
                candidate.vision_score = result.score
                candidate.vision_labels = result.labels
                candidate.is_product_image = result.is_product_image
                candidate.has_text = result.has_text
                
                logger.info(f"✨ New best image: score={result.score:.2f}, labels={result.labels[:3]}")
            
            # If we find a really good image, stop early
            if result.score >= 0.8:
                logger.info(f"Found excellent image (score={result.score:.2f}), stopping search")
                break
        else:
            # Without Vision AI, just use the first valid image
            if best_content is None:
                best_content = content
                best_candidate = candidate
                best_result = VisionAnalysisResult(
                    is_valid=True, score=0.5, labels=[], is_product_image=True,
                    has_text=False, has_logo=False, safe_search_ok=True,
                    dominant_colors=[], error="Vision AI not used"
                )
                break
    
    if best_content:
        score_str = f"{best_score:.2f}" if best_score >= 0 else "N/A"
        source_str = best_candidate.source if best_candidate else "unknown"
        logger.info(f"✅ Selected best image for {sku}: score={score_str}, source={source_str}")
    else:
        logger.warning(f"No valid images found for: {product_name}")
    
    return best_content, best_candidate, best_result


def search_validate_and_save(
    product_name: str,
    sku: str,
    output_dir: Path,
    ean: str = "",
    category: str = "",
    max_candidates: int = 5,
    use_vision_ai: bool = True
) -> Tuple[Optional[Path], Optional[VisionAnalysisResult]]:
    """
    Complete pipeline: search, validate with Vision AI, and save best image.
    
    Args:
        product_name: Name of the product
        sku: Product SKU (used for filename)
        output_dir: Directory to save the image
        ean: Product EAN barcode
        category: Product category
        max_candidates: Maximum candidates to evaluate
        use_vision_ai: Whether to use Vision AI for validation
    
    Returns:
        (saved_path, vision_result) or (None, None)
    """
    content, candidate, result = search_and_validate_best_image(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_candidates=max_candidates,
        use_vision_ai=use_vision_ai
    )
    
    if not content:
        return None, None
    
    saved_path = process_and_save_image(content, sku, output_dir)
    
    if saved_path:
        score_str = f"{result.score:.2f}" if result else "N/A"
        logger.info(f"🖼️  Image saved: {saved_path.name} (Vision score: {score_str})")
    
    return saved_path, result
