#!/usr/bin/env python3
"""
Upload product images to server via FTP.

This script uploads images from data/images to the server via FTP,
making them accessible at the IMAGE_BASE_URL.

Usage:
    python scripts/upload_images_ftp.py --dry-run  # Simulate
    python scripts/upload_images_ftp.py            # Upload all
    python scripts/upload_images_ftp.py --category racao  # Specific category
    python scripts/upload_images_ftp.py --limit 10  # Test with 10 images
"""

import argparse
import ftplib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# FTP credentials from environment
FTP_HOST = os.getenv("IMAGE_FTP_HOST", "")
FTP_USER = os.getenv("IMAGE_FTP_USER", "")
FTP_PASSWORD = os.getenv("IMAGE_FTP_PASSWORD", "")
FTP_PORT = int(os.getenv("IMAGE_FTP_PORT", "21"))
REMOTE_PATH = os.getenv("IMAGE_REMOTE_PATH", "")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "")

# Paths
IMAGES_DIR = Path("data/images")
REPORT_DIR = Path("data/reports")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def connect_ftp() -> ftplib.FTP:
    """Connect to FTP server."""
    if not FTP_HOST or not FTP_USER or not FTP_PASSWORD:
        logger.error("FTP credentials not configured in .env")
        sys.exit(1)
    
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=30)
        ftp.login(FTP_USER, FTP_PASSWORD)
        logger.info(f"✅ Connected to FTP server: {FTP_HOST}")
        return ftp
    except Exception as e:
        logger.error(f"Failed to connect to FTP: {e}")
        sys.exit(1)


def ensure_remote_directory(ftp: ftplib.FTP, remote_dir: str):
    """Ensure remote directory exists, create if not (supports nested paths)."""
    # Split path and create each directory level
    parts = remote_dir.replace('\\', '/').strip('/').split('/')
    current_path = ""
    
    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else f"/{part}"
        try:
            ftp.cwd(current_path)
        except ftplib.error_perm:
            # Directory doesn't exist, create it
            logger.info(f"Creating remote directory: {current_path}")
            try:
                ftp.mkd(current_path)
                ftp.cwd(current_path)
            except Exception as e:
                logger.error(f"Failed to create directory {current_path}: {e}")
                raise


def upload_file_ftp(ftp: ftplib.FTP, local_path: Path, remote_filename: str) -> bool:
    """Upload file to FTP server."""
    try:
        with open(local_path, 'rb') as f:
            ftp.storbinary(f'STOR {remote_filename}', f)
        return True
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return False


def find_images(category: str = None, sku: str = None) -> List[Path]:
    """Find images in data/images directory."""
    images = []
    
    if sku:
        # Search for specific SKU
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            img_path = IMAGES_DIR / f"{sku}{ext}"
            if img_path.exists():
                images.append(img_path)
                break
    elif category:
        # Search in specific category folder
        category_dir = IMAGES_DIR / category
        if category_dir.exists():
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                images.extend(category_dir.glob(f"*{ext}"))
    else:
        # Search all images
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            images.extend(IMAGES_DIR.rglob(f"*{ext}"))
    
    return sorted(images)


def main():
    parser = argparse.ArgumentParser(description="Upload images to server via FTP")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    parser.add_argument("--sku", type=str, help="Upload image for specific SKU")
    parser.add_argument("--category", type=str, help="Upload images from specific category folder")
    parser.add_argument("--limit", type=int, help="Limit number of images to upload")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("📤 FTP - UPLOAD PRODUCT IMAGES")
    print("=" * 80)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No uploads will be made")
    
    if args.sku:
        print(f"🎯 Uploading image for SKU: {args.sku}")
    elif args.category:
        print(f"📁 Uploading images from category: {args.category}")
    else:
        print("📁 Uploading all images")
    
    print(f"🌐 Base URL: {IMAGE_BASE_URL}")
    print(f"📂 Remote path: {REMOTE_PATH}")
    print("=" * 80)
    print()
    
    # Find images
    logger.info("Finding images...")
    images = find_images(category=args.category, sku=args.sku)
    
    if not images:
        logger.warning("No images found!")
        return
    
    logger.info(f"Found {len(images)} images")
    
    # Apply limit
    if args.limit and args.limit > 0:
        images = images[:args.limit]
        logger.info(f"Limited to {len(images)} images")
    
    # Show examples
    print()
    print("📋 IMAGES TO UPLOAD (first 10):")
    for img in images[:10]:
        sku = img.stem
        url = f"{IMAGE_BASE_URL}{img.name}"
        print(f"  {sku:20s} | {img.name:30s} | {url}")
    if len(images) > 10:
        print(f"  ... and {len(images) - 10} more")
    print()
    
    if args.dry_run:
        logger.info("✅ DRY RUN COMPLETE - No uploads were made")
        return
    
    # Confirm
    confirm = input("⚠️  Proceed with upload? Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        logger.info("❌ Aborted by user")
        return
    print()
    
    # Connect to FTP
    logger.info("Connecting to FTP server...")
    ftp = connect_ftp()
    
    # Ensure remote directory exists
    logger.info(f"Checking remote directory: {REMOTE_PATH}")
    ensure_remote_directory(ftp, REMOTE_PATH)
    
    # Process images
    logger.info("Uploading images...")
    print()
    
    results = {
        'uploaded': [],
        'failed': [],
        'skipped': []
    }
    
    current_category = None
    
    for i, img_path in enumerate(images, 1):
        filename = img_path.name
        
        # Get category from parent folder (e.g., data/images/racao -> racao)
        category = img_path.parent.name if img_path.parent.name != "images" else "sem_categoria"
        
        logger.info(f"[{i}/{len(images)}] Uploading {category}/{filename}...")
        
        # Change to category directory if needed
        if category != current_category:
            category_path = f"{REMOTE_PATH.rstrip('/')}/{category}"
            logger.info(f"  📁 Switching to: {category_path}")
            ensure_remote_directory(ftp, category_path)
            current_category = category
        
        # Check if file already exists
        try:
            existing_files = ftp.nlst()
            if filename in existing_files:
                logger.info(f"  ⏭️  File already exists, skipping")
                results['skipped'].append(f"{category}/{filename}")
                continue
        except:
            pass  # Directory might be empty
        
        # Upload
        success = upload_file_ftp(ftp, img_path, filename)
        
        if success:
            url = f"{IMAGE_BASE_URL.rstrip('/')}/{category}/{filename}"
            logger.info(f"  ✅ Uploaded: {url}")
            results['uploaded'].append(f"{category}/{filename}")
        else:
            logger.error(f"  ❌ Upload failed")
            results['failed'].append(f"{category}/{filename}")
        
        # Small delay to avoid overwhelming server
        time.sleep(0.1)
    
    # Close FTP connection
    ftp.quit()
    logger.info("FTP connection closed")
    
    # Summary
    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total processed:    {len(images)}")
    print(f"Successfully uploaded: {len(results['uploaded'])}")
    print(f"Already existed:    {len(results['skipped'])}")
    print(f"Failed:             {len(results['failed'])}")
    print("=" * 80)
    
    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"ftp_upload_{timestamp}.json"
    
    report = {
        "timestamp": timestamp,
        "category": args.category,
        "sku": args.sku,
        "total_processed": len(images),
        "base_url": IMAGE_BASE_URL,
        "results": results
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Report saved: {report_file}")
    
    print()
    print("✅ UPLOAD COMPLETE!")
    print(f"📸 Images are now accessible at: {IMAGE_BASE_URL}")


if __name__ == "__main__":
    main()
