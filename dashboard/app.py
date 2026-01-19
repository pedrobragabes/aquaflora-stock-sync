"""
AquaFlora Stock Sync - Web Dashboard
FastAPI application for controlling stock synchronization.
"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from contextlib import asynccontextmanager
import secrets

# APScheduler for scheduled sync
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.database import ProductDatabase
from src.image_curator import ImageCurator
from src.image_scraper import search_and_get_thumbnails

logger = logging.getLogger(__name__)

# Global state
class AppState:
    is_syncing: bool = False
    last_sync: Optional[datetime] = None
    sync_status: str = "Idle"
    scheduler_enabled: bool = False
    scheduled_time: str = "11:00"

state = AppState()

# Global scheduler instance
scheduler = AsyncIOScheduler()
SCHEDULER_JOB_ID = "daily_sync"
WHITELIST_JOB_ID = "weekly_whitelist"

# Security for Basic Auth
security = HTTPBasic()

# Metrics tracking
metrics = {
    "syncs_total": 0,
    "syncs_success": 0,
    "syncs_failed": 0,
    "products_updated": 0,
    "last_sync_duration_seconds": 0.0,
    "whitelist_refreshes": 0,
}


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify HTTP Basic Auth credentials.
    Only enforced if dashboard_auth_enabled is True.
    """
    if not settings.dashboard_auth_enabled:
        return "anonymous"
    
    if not settings.dashboard_password:
        return "anonymous"  # No password set, allow access
    
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        settings.dashboard_username.encode("utf8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        settings.dashboard_password.encode("utf8")
    )
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username


def get_auth_dependency():
    """Return auth dependency only if auth is enabled."""
    if settings.dashboard_auth_enabled and settings.dashboard_password:
        return [Depends(verify_auth)]
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Dashboard starting...")
    scheduler.start()
    logger.info("⏰ Scheduler started")
    
    # Add weekly whitelist refresh (Sunday 3 AM)
    try:
        scheduler.add_job(
            refresh_whitelist_job,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id=WHITELIST_JOB_ID,
            replace_existing=True,
            name="Weekly whitelist refresh"
        )
        logger.info("📋 Weekly whitelist refresh scheduled (Sunday 3 AM)")
    except Exception as e:
        logger.warning(f"Failed to schedule whitelist refresh: {e}")
    
    yield
    scheduler.shutdown()
    logger.info("👋 Dashboard shutting down...")


app = FastAPI(
    title="AquaFlora Stock Sync",
    description="""
## Dashboard de Controle de Sincronização de Estoque

**API para gerenciar sincronização entre Athos ERP e WooCommerce.**

### Funcionalidades:
- 📦 Sincronização de produtos
- 📊 Métricas e estatísticas
- ⏰ Agendamento automático
- 📋 Mapeamento de whitelist

### Documentação:
- `/docs` - Swagger UI interativo
- `/redoc` - ReDoc documentação
""",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount static files and templates
static_path = Path(__file__).parent / "static"
templates_path = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_dashboard_stats() -> dict:
    """Get stats for dashboard display."""
    try:
        db = ProductDatabase(settings.db_path)
        stats = db.get_stats()
        whitelist_count = db.get_site_products_count()
        db.close()
        
        return {
            "total_products": stats.get("total_products", 0),
            "whitelist_count": whitelist_count,
            "last_synced": stats.get("last_synced", 0),
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return {"total_products": 0, "whitelist_count": 0, "last_synced": 0}


def get_last_run_stats() -> Optional[dict]:
    """Load last run stats from JSON."""
    stats_path = Path("last_run_stats.json")
    if stats_path.exists():
        try:
            with open(stats_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def get_input_files() -> list:
    """Get list of CSV files in input directory."""
    input_dir = settings.input_dir
    if not input_dir.exists():
        return []
    
    files = []
    for f in input_dir.glob("*.csv"):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M"),
        })
    
    return sorted(files, key=lambda x: x["modified"], reverse=True)


def scheduled_sync_job():
    """
    Job function called by APScheduler at scheduled time.
    Finds the latest CSV and runs sync in lite mode.
    """
    logger.info("⏰ Scheduled sync job triggered")
    
    input_dir = settings.input_dir
    if not input_dir.exists():
        logger.warning("📭 Input directory not found for scheduled sync")
        return
    
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        logger.warning("📭 No CSV files found for scheduled sync")
        return
    
    # Get the most recent file
    latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
    logger.info(f"📁 Running scheduled sync with: {latest_file.name}")
    
    # Import here to avoid circular import
    from main import process_file
    
    state.is_syncing = True
    state.sync_status = "Sync agendado..."
    
    import time as time_module
    start_time = time_module.time()
    metrics["syncs_total"] += 1
    
    try:
        summary = process_file(
            latest_file,
            dry_run=False,
            lite_mode=True,  # Scheduled sync always uses lite mode
            allow_create=False,
        )
        state.last_sync = datetime.now()
        state.sync_status = "Agendado ✅" if summary.success else "Erro ❌"
        
        # Update metrics
        metrics["syncs_success"] += 1
        metrics["products_updated"] += summary.total_synced
        metrics["last_sync_duration_seconds"] = round(time_module.time() - start_time, 2)
        
        logger.info(f"✅ Scheduled sync completed: {summary.total_synced} products")
    except Exception as e:
        logger.error(f"❌ Scheduled sync failed: {e}")
        state.sync_status = f"Erro agendado: {str(e)[:30]}"
        metrics["syncs_failed"] += 1
    finally:
        state.is_syncing = False


def refresh_whitelist_job():
    """
    Job function to refresh whitelist from WooCommerce.
    Called weekly by scheduler.
    """
    logger.info("🔄 Auto-refreshing whitelist from WooCommerce...")
    
    try:
        from main import map_site_products
        map_site_products()
        metrics["whitelist_refreshes"] += 1
        logger.info("✅ Whitelist refresh completed")
    except Exception as e:
        logger.error(f"❌ Whitelist refresh failed: {e}")


async def run_sync_task(filepath: Path, lite_mode: bool = True, allow_create: bool = False):
    """Run sync in background."""
    from main import process_file
    
    state.is_syncing = True
    state.sync_status = "Processando..."
    
    try:
        summary = process_file(
            filepath,
            dry_run=False,
            lite_mode=lite_mode,
            allow_create=allow_create,
        )
        state.last_sync = datetime.now()
        state.sync_status = "Concluído ✅" if summary.success else "Erro ❌"
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        state.sync_status = f"Erro: {str(e)[:50]}"
    finally:
        state.is_syncing = False


# =============================================================================
# PAGE ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main dashboard page."""
    stats = get_dashboard_stats()
    last_run = get_last_run_stats()
    input_files = get_input_files()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "last_run": last_run,
        "input_files": input_files,
        "state": state,
        "settings": settings,
    })


@app.get("/images", response_class=HTMLResponse)
async def images_page(request: Request):
    """Image curation page."""
    try:
        db = ProductDatabase(settings.db_path)
        curator = ImageCurator(db)
        stats = curator.get_stats()
        curator.close()
        db.close()
    except Exception as e:
        logger.error(f"Failed to get image stats: {e}")
        stats = {"pending_count": 0, "curated_count": 0}
    
    return templates.TemplateResponse("images.html", {
        "request": request,
        "stats": stats,
        "state": state,
    })


# =============================================================================
# API ROUTES
# =============================================================================

@app.get("/api/status")
async def api_status():
    """Get current sync status."""
    stats = get_dashboard_stats()
    last_run = get_last_run_stats()
    
    return {
        "is_syncing": state.is_syncing,
        "sync_status": state.sync_status,
        "last_sync": state.last_sync.isoformat() if state.last_sync else None,
        "scheduler_enabled": state.scheduler_enabled,
        "scheduled_time": state.scheduled_time,
        "stats": stats,
        "last_run": last_run,
    }


@app.get("/metrics")
async def get_metrics():
    """
    Get application metrics for monitoring.
    Returns sync counts, durations, and success rates.
    """
    stats = get_dashboard_stats()
    
    return {
        **metrics,
        "whitelist_count": stats.get("whitelist_count", 0),
        "total_products_in_db": stats.get("total_products", 0),
        "is_syncing": state.is_syncing,
        "scheduler_enabled": state.scheduler_enabled,
    }


@app.post("/api/sync/run")
async def api_run_sync(
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    lite_mode: bool = Form(True),
    allow_create: bool = Form(False),
):
    """Trigger a sync operation."""
    if state.is_syncing:
        return JSONResponse(
            {"success": False, "message": "Sync já em andamento!"},
            status_code=409,
        )
    
    filepath = settings.input_dir / filename
    if not filepath.exists():
        return JSONResponse(
            {"success": False, "message": f"Arquivo não encontrado: {filename}"},
            status_code=404,
        )
    
    # Run in background
    background_tasks.add_task(run_sync_task, filepath, lite_mode, allow_create)
    
    return {"success": True, "message": f"Sync iniciado: {filename}"}


@app.post("/api/sync/upload")
async def api_upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file to input directory."""
    if not file.filename.endswith('.csv'):
        return JSONResponse(
            {"success": False, "message": "Apenas arquivos CSV são aceitos"},
            status_code=400,
        )
    
    # Save file
    filepath = settings.input_dir / file.filename
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        content = await file.read()
        with open(filepath, 'wb') as f:
            f.write(content)
        
        return {"success": True, "message": f"Upload concluído: {file.filename}"}
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": str(e)},
            status_code=500,
        )


@app.get("/api/products")
async def api_products():
    """Get last product changes."""
    last_run = get_last_run_stats()
    if not last_run:
        return {"products": []}
    
    return {"products": last_run.get("product_changes", [])[:20]}


@app.post("/api/map-site")
async def api_map_site(background_tasks: BackgroundTasks):
    """Run --map-site to refresh whitelist."""
    if state.is_syncing:
        return JSONResponse(
            {"success": False, "message": "Operação em andamento!"},
            status_code=409,
        )
    
    async def run_map():
        from main import map_site_products
        state.is_syncing = True
        state.sync_status = "Mapeando site..."
        try:
            map_site_products()
            state.sync_status = "Mapeamento concluído ✅"
        except Exception as e:
            state.sync_status = f"Erro: {str(e)[:50]}"
        finally:
            state.is_syncing = False
    
    background_tasks.add_task(run_map)
    return {"success": True, "message": "Mapeamento iniciado..."}


@app.post("/api/schedule")
async def api_schedule(
    enabled: bool = Form(...),
    time: str = Form("11:00"),
):
    """Configure scheduled sync with APScheduler."""
    try:
        # Parse time
        parts = time.split(":")
        hour = int(parts[0]) if len(parts) >= 1 else 11
        minute = int(parts[1]) if len(parts) >= 2 else 0
        
        if enabled:
            # Remove existing job if any
            try:
                scheduler.remove_job(SCHEDULER_JOB_ID)
            except Exception:
                pass  # Job didn't exist
            
            # Add new job with CronTrigger
            scheduler.add_job(
                scheduled_sync_job,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=SCHEDULER_JOB_ID,
                replace_existing=True,
                name="Daily stock sync"
            )
            logger.info(f"⏰ Scheduled sync job set for {hour:02d}:{minute:02d}")
            message = f"Agendamento ativado para {hour:02d}:{minute:02d}"
        else:
            # Remove job
            try:
                scheduler.remove_job(SCHEDULER_JOB_ID)
                logger.info("⏰ Scheduled sync job removed")
            except Exception:
                pass  # Job didn't exist
            message = "Agendamento desativado"
        
        state.scheduler_enabled = enabled
        state.scheduled_time = time
        
        return {"success": True, "message": message}
        
    except ValueError as e:
        return JSONResponse(
            {"success": False, "message": f"Horário inválido: {time}"},
            status_code=400,
        )
    except Exception as e:
        logger.error(f"Failed to configure scheduler: {e}")
        return JSONResponse(
            {"success": False, "message": f"Erro ao configurar: {str(e)[:50]}"},
            status_code=500,
        )


# =============================================================================
# HTMX PARTIALS
# =============================================================================

@app.get("/partials/status", response_class=HTMLResponse)
async def partial_status(request: Request):
    """HTMX partial for status badge."""
    return templates.TemplateResponse("partials/status.html", {
        "request": request,
        "state": state,
    })


@app.get("/partials/files", response_class=HTMLResponse)
async def partial_files(request: Request):
    """HTMX partial for file list."""
    input_files = get_input_files()
    return templates.TemplateResponse("partials/files.html", {
        "request": request,
        "input_files": input_files,
    })


@app.get("/partials/products", response_class=HTMLResponse)
async def partial_products(request: Request):
    """HTMX partial for product changes list."""
    last_run = get_last_run_stats()
    products = last_run.get("product_changes", [])[:10] if last_run else []
    return templates.TemplateResponse("partials/products.html", {
        "request": request,
        "products": products,
    })


# =============================================================================
# IMAGE CURATION ROUTES
# =============================================================================

@app.get("/partials/pending-list", response_class=HTMLResponse)
async def partial_pending_list(request: Request):
    """HTMX partial for pending products list."""
    try:
        db = ProductDatabase(settings.db_path)
        pending = db.get_pending_images(limit=50)
        db.close()
        
        # Add product names from last run stats if available
        last_run = get_last_run_stats()
        product_names = {}
        if last_run:
            for change in last_run.get("product_changes", []):
                if "sku" in change and "name" in change:
                    product_names[change["sku"]] = change["name"]
        
        for p in pending:
            p["name"] = product_names.get(p["sku"], p["sku"])
        
    except Exception as e:
        logger.error(f"Failed to get pending images: {e}")
        pending = []
    
    return templates.TemplateResponse("partials/pending_list.html", {
        "request": request,
        "pending": pending,
    })


@app.get("/api/images/search/{sku}", response_class=HTMLResponse)
async def api_search_images(request: Request, sku: str):
    """Search images for a product and return HTMX partial."""
    try:
        # Get product name from database or use SKU
        db = ProductDatabase(settings.db_path)
        record = db.get_record(sku)
        db.close()
        
        # Use SKU as product name if no record found
        product_name = sku
        if record:
            # Try to get name from last run
            last_run = get_last_run_stats()
            if last_run:
                for change in last_run.get("product_changes", []):
                    if change.get("sku") == sku:
                        product_name = change.get("name", sku)
                        break
        
        # Search for images
        candidates = search_and_get_thumbnails(
            product_name=product_name,
            sku=sku,
            max_results=6
        )
        
    except Exception as e:
        logger.error(f"Image search failed for SKU {sku}: {e}")
        candidates = []
    
    return templates.TemplateResponse("partials/image_candidates.html", {
        "request": request,
        "candidates": candidates,
    })


@app.post("/api/images/select")
async def api_select_image(
    sku: str = Form(...),
    image_url: str = Form(...),
):
    """Save selected image for a product."""
    try:
        db = ProductDatabase(settings.db_path)
        curator = ImageCurator(db)
        
        success = curator.save_selection(
            sku=sku,
            image_url=image_url,
            download=True
        )
        
        curator.close()
        db.close()
        
        if success:
            return HTMLResponse(
                '<div class="alert alert-success">✅ Imagem salva para ' + sku + '</div>'
            )
        else:
            return HTMLResponse(
                '<div class="alert alert-error">❌ Erro ao salvar imagem</div>'
            )
            
    except Exception as e:
        logger.error(f"Failed to save image for SKU {sku}: {e}")
        return HTMLResponse(
            '<div class="alert alert-error">❌ Erro: ' + str(e)[:50] + '</div>'
        )


@app.post("/api/images/apply-family")
async def api_apply_family(sku: str = Form(...)):
    """Apply image to product family (same prefix)."""
    try:
        db = ProductDatabase(settings.db_path)
        curator = ImageCurator(db)
        
        count = curator.apply_to_family(sku)
        
        curator.close()
        db.close()
        
        return HTMLResponse(
            f'<div class="alert alert-success">👨‍👩‍👧‍👦 Imagem aplicada para {count} produtos da família</div>'
        )
        
    except Exception as e:
        logger.error(f"Failed to apply family for SKU {sku}: {e}")
        return HTMLResponse(
            '<div class="alert alert-error">❌ Erro: ' + str(e)[:50] + '</div>'
        )


@app.get("/api/images/stats")
async def api_image_stats():
    """Get image curation statistics."""
    try:
        db = ProductDatabase(settings.db_path)
        curator = ImageCurator(db)
        stats = curator.get_stats()
        curator.close()
        db.close()
        return stats
    except Exception as e:
        logger.error(f"Failed to get image stats: {e}")
        return {"pending_count": 0, "curated_count": 0, "uploaded_count": 0}


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    print("🖥️  AquaFlora Stock Sync - Dashboard")
    print("   Acesse: http://localhost:8080")
    print("   Pressione Ctrl+C para parar")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
