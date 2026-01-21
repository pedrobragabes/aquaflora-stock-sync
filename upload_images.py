#!/usr/bin/env python3
"""
AquaFlora Stock Sync - Image Uploader
Upload product images to WordPress server via FTP/SFTP.

Usage:
    python upload_images.py                    # Upload all pending images
    python upload_images.py --sku 7898586130210   # Upload specific SKU
    python upload_images.py --dry-run          # Show what would be uploaded
    python upload_images.py --verify           # Verify images on server

Prerequisites:
    1. Configure .env with FTP/SFTP credentials:
       IMAGE_BASE_URL=https://aquafloragroshop.com.br/wp-content/uploads/produtos/
       IMAGE_FTP_HOST=aquafloragroshop.com.br
       IMAGE_FTP_USER=seu_usuario
       IMAGE_FTP_PASSWORD=sua_senha
       IMAGE_FTP_PORT=21
       IMAGE_USE_SFTP=false
       IMAGE_REMOTE_PATH=/wp-content/uploads/produtos/
    
    2. Images should be in data/images/ folder with SKU.jpg naming
"""

import argparse
import ftplib
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Check if paramiko is available for SFTP
HAS_PARAMIKO = False
try:
    import paramiko  # type: ignore  # noqa: F401
    HAS_PARAMIKO = True
except ImportError:
    pass

from config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Directories
LOCAL_IMAGES_DIR = Path("data/images")
UPLOAD_LOG_FILE = Path("data/upload_log.txt")


def get_local_images() -> List[Path]:
    """Get list of local image files."""
    if not LOCAL_IMAGES_DIR.exists():
        return []
    return list(LOCAL_IMAGES_DIR.glob("*.jpg"))


def get_uploaded_skus() -> set:
    """Get set of SKUs that were already uploaded."""
    if not UPLOAD_LOG_FILE.exists():
        return set()
    
    with open(UPLOAD_LOG_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def mark_as_uploaded(sku: str):
    """Mark a SKU as uploaded."""
    UPLOAD_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{sku}\n")


def ftp_mkdir_recursive(ftp: ftplib.FTP, remote_path: str):
    """Create directory recursively on FTP server."""
    dirs = remote_path.strip('/').split('/')
    current = ""
    for d in dirs:
        current += f"/{d}"
        try:
            ftp.cwd(current)
        except ftplib.error_perm:
            try:
                ftp.mkd(current)
                logger.info(f"📁 Created directory: {current}")
            except ftplib.error_perm as e:
                # Directory might already exist or permission denied
                if "exists" not in str(e).lower():
                    raise


def upload_via_ftp(local_path: Path, remote_filename: str, dry_run: bool = False) -> bool:
    """Upload a file via FTP."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would upload: {local_path.name} → {remote_filename}")
        return True
    
    try:
        ftp = ftplib.FTP()
        ftp.connect(settings.image_ftp_host, settings.image_ftp_port, timeout=30)
        ftp.login(settings.image_ftp_user, settings.image_ftp_password)
        
        # Navigate to remote directory (create recursively if needed)
        remote_path = settings.image_remote_path.rstrip('/')
        try:
            ftp.cwd(remote_path)
        except ftplib.error_perm:
            # Create directory structure recursively
            ftp_mkdir_recursive(ftp, remote_path)
            ftp.cwd(remote_path)
        
        # Upload file
        with open(local_path, 'rb') as f:
            ftp.storbinary(f'STOR {remote_filename}', f)
        
        ftp.quit()
        logger.info(f"✅ Uploaded: {local_path.name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ FTP Error uploading {local_path.name}: {e}")
        return False


def upload_via_sftp(local_path: Path, remote_filename: str, dry_run: bool = False) -> bool:
    """Upload a file via SFTP."""
    if not HAS_PARAMIKO:
        logger.error("❌ SFTP requires paramiko. Install with: pip install paramiko")
        return False
    
    if dry_run:
        logger.info(f"[DRY-RUN] Would upload (SFTP): {local_path.name} → {remote_filename}")
        return True
    
    try:
        # Import here to avoid issues when paramiko is not installed
        import paramiko as ssh  # type: ignore
        
        transport = ssh.Transport((settings.image_ftp_host, settings.image_ftp_port or 22))
        transport.connect(username=settings.image_ftp_user, password=settings.image_ftp_password)
        sftp = ssh.SFTPClient.from_transport(transport)
        
        if sftp is None:
            raise Exception("Failed to create SFTP client")
        
        remote_path = settings.image_remote_path.rstrip('/')
        remote_full_path = f"{remote_path}/{remote_filename}"
        
        # Ensure remote directory exists
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            logger.info(f"Creating remote directory: {remote_path}")
            sftp.mkdir(remote_path)
        
        # Upload file
        sftp.put(str(local_path), remote_full_path)
        
        sftp.close()
        transport.close()
        
        logger.info(f"✅ Uploaded (SFTP): {local_path.name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ SFTP Error uploading {local_path.name}: {e}")
        return False


def upload_image(local_path: Path, dry_run: bool = False) -> bool:
    """Upload a single image using configured method (FTP or SFTP)."""
    remote_filename = local_path.name
    
    if settings.image_use_sftp:
        return upload_via_sftp(local_path, remote_filename, dry_run)
    else:
        return upload_via_ftp(local_path, remote_filename, dry_run)


def verify_remote_image(sku: str) -> bool:
    """Verify if an image exists on the remote server."""
    import requests
    
    if not settings.image_base_url:
        logger.error("IMAGE_BASE_URL not configured")
        return False
    
    url = f"{settings.image_base_url.rstrip('/')}/{sku}.jpg"
    
    try:
        response = requests.head(url, timeout=10)
        exists = response.status_code == 200
        
        if exists:
            logger.info(f"✅ {sku}: Image exists at {url}")
        else:
            logger.warning(f"❌ {sku}: Image NOT found (HTTP {response.status_code})")
        
        return exists
    except Exception as e:
        logger.error(f"❌ {sku}: Error checking URL: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Upload product images to server")
    parser.add_argument("--sku", type=str, help="Upload specific SKU only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    parser.add_argument("--force", action="store_true", help="Re-upload even if already uploaded")
    parser.add_argument("--verify", action="store_true", help="Verify images exist on server")
    parser.add_argument("--all", action="store_true", help="Upload all images (including previously uploaded)")
    args = parser.parse_args()
    
    # Check configuration
    if not args.verify:
        if not settings.image_ftp_host:
            logger.error("❌ IMAGE_FTP_HOST not configured in .env")
            logger.error("   Configure as variáveis de ambiente para upload:")
            logger.error("   IMAGE_FTP_HOST=seu-servidor.com.br")
            logger.error("   IMAGE_FTP_USER=usuario")
            logger.error("   IMAGE_FTP_PASSWORD=senha")
            logger.error("   IMAGE_REMOTE_PATH=/wp-content/uploads/produtos/")
            logger.error("   IMAGE_BASE_URL=https://seu-site.com.br/wp-content/uploads/produtos/")
            sys.exit(1)
    
    if not settings.image_base_url:
        logger.warning("⚠️  IMAGE_BASE_URL not configured - CSV will not have image URLs!")
    
    print("\n" + "="*60)
    print("📤 AquaFlora Image Uploader")
    print("="*60)
    
    if args.verify:
        # Verification mode
        local_images = get_local_images()
        print(f"\n🔍 Verificando {len(local_images)} imagens no servidor...\n")
        
        found = 0
        missing = 0
        
        for img in local_images:
            sku = img.stem
            if args.sku and sku != args.sku:
                continue
            
            if verify_remote_image(sku):
                found += 1
            else:
                missing += 1
        
        print(f"\n📊 Resultado: {found} encontradas, {missing} faltando")
        return
    
    # Upload mode
    local_images = get_local_images()
    uploaded_skus = get_uploaded_skus() if not args.all else set()
    
    if args.sku:
        # Single SKU mode
        img_path = LOCAL_IMAGES_DIR / f"{args.sku}.jpg"
        if not img_path.exists():
            logger.error(f"❌ Image not found: {img_path}")
            sys.exit(1)
        
        local_images = [img_path]
        uploaded_skus = set() if args.force else uploaded_skus
    
    # Filter out already uploaded
    pending = [img for img in local_images if img.stem not in uploaded_skus]
    
    print(f"\n📁 Imagens locais: {len(local_images)}")
    print(f"✅ Já enviadas: {len(uploaded_skus)}")
    print(f"⏳ Pendentes: {len(pending)}")
    
    if settings.image_use_sftp:
        print(f"🔒 Método: SFTP (porta {settings.image_ftp_port or 22})")
    else:
        print(f"📡 Método: FTP (porta {settings.image_ftp_port})")
    
    print(f"🌐 Servidor: {settings.image_ftp_host}")
    print(f"📂 Pasta remota: {settings.image_remote_path}")
    print(f"🔗 URL base: {settings.image_base_url or '(não configurada)'}")
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN - Nenhuma imagem será realmente enviada\n")
    
    if not pending:
        print("\n✨ Todas as imagens já foram enviadas!")
        return
    
    print(f"\n🚀 Iniciando upload de {len(pending)} imagens...\n")
    
    success = 0
    failed = 0
    
    for i, img_path in enumerate(pending, 1):
        sku = img_path.stem
        print(f"[{i}/{len(pending)}] {sku}...", end=" ")
        
        if upload_image(img_path, dry_run=args.dry_run):
            success += 1
            if not args.dry_run:
                mark_as_uploaded(sku)
            print("✅")
        else:
            failed += 1
            print("❌")
    
    print("\n" + "="*60)
    print(f"📊 RESULTADO: {success} enviadas, {failed} falhas")
    print("="*60)
    
    if success > 0 and not args.dry_run:
        print(f"\n🔗 As imagens estão disponíveis em:")
        print(f"   {settings.image_base_url or 'Configure IMAGE_BASE_URL no .env'}")
        print(f"\n💡 Agora rode 'python main.py --input ...' para gerar o CSV com as URLs")


if __name__ == "__main__":
    main()
