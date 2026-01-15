"""
AquaFlora Stock Sync - Premium Notification Service
Sends rich sync reports via Discord/Telegram webhooks.
"""

import logging
from typing import Optional

import httpx

from .models import SyncSummary, ProductChange

logger = logging.getLogger(__name__)

# AquaFlora branding
AQUAFLORA_LOGO = "https://aquafloragroshop.com.br/wp-content/uploads/2021/08/cropped-logo-aquaflora-agroshop-1.png"

# Status colors (Semaphore system)
COLOR_SUCCESS = 0x2ECC71  # Green
COLOR_WARNING = 0xF1C40F  # Yellow
COLOR_ERROR = 0xE74C3C   # Red


class NotificationService:
    """
    Sends premium sync reports via webhooks.
    
    Features:
    - Rich Discord embeds with logo and colors
    - Top 10 product changes with price diffs
    - Semaphore color system (Green/Yellow/Red)
    - Price Guard alerts
    """
    
    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        telegram_webhook_url: Optional[str] = None,
    ):
        self.discord_url = discord_webhook_url
        self.telegram_url = telegram_webhook_url
        self._client = httpx.Client(timeout=30.0)
    
    def send_report(self, summary: SyncSummary):
        """Send sync report to all configured webhooks."""
        if self.discord_url:
            self._send_discord_rich(summary)
        
        if self.telegram_url:
            self._send_telegram(summary)
    
    def _determine_status(self, summary: SyncSummary) -> tuple:
        """Determine status color and emoji based on sync result."""
        if not summary.success or summary.errors:
            return COLOR_ERROR, "❌", "ERRO"
        elif summary.price_warnings:
            return COLOR_WARNING, "⚠️", "ATENÇÃO"
        else:
            return COLOR_SUCCESS, "✅", "SUCESSO"
    
    def _format_price_change(self, change: ProductChange) -> str:
        """Format a single product change for display."""
        emoji = change.price_direction
        name = change.name[:30] + "..." if len(change.name) > 30 else change.name
        
        if change.old_price is not None:
            # Existing product with price change
            variation_str = f"{change.price_variation:+.1f}%" if change.price_variation != 0 else "="
            return f"{emoji} `{change.sku}` | **{name}**\nR$ {change.old_price:.2f} ➔ R$ {change.new_price:.2f} ({variation_str})"
        else:
            # New product
            return f"{emoji} `{change.sku}` | **{name}**\nR$ {change.new_price:.2f} (NOVO)"
    
    def _send_discord_rich(self, summary: SyncSummary):
        """Send premium Discord webhook with rich embed."""
        try:
            color, emoji, status_text = self._determine_status(summary)
            
            # Build description with summary stats
            description = f"**{emoji} {status_text}** - Sincronização concluída às {summary.timestamp.strftime('%H:%M:%S')}"
            
            # Main stats fields
            fields = [
                {
                    "name": "📊 Processados",
                    "value": f"**{summary.total_parsed}** produtos",
                    "inline": True
                },
                {
                    "name": "✨ Novos",
                    "value": f"**{summary.new_products}**",
                    "inline": True
                },
                {
                    "name": "🔄 Atualizados",
                    "value": f"**{summary.full_updates + summary.fast_updates}**",
                    "inline": True
                },
                {
                    "name": "⏭️ Ignorados",
                    "value": f"**{summary.skipped}**",
                    "inline": True
                },
            ]
            
            # TOP 10 Product Changes (Highlight Section)
            if summary.product_changes:
                # Get top 10 most significant changes (by absolute variation)
                significant_changes = sorted(
                    [c for c in summary.product_changes if c.change_type in ('new', 'updated')],
                    key=lambda x: abs(x.price_variation),
                    reverse=True
                )[:10]
                
                if significant_changes:
                    changes_text = "\n".join([
                        self._format_price_change(c) for c in significant_changes
                    ])
                    
                    fields.append({
                        "name": "📋 Destaques (Top 10 Alterações)",
                        "value": changes_text[:1024],  # Discord limit
                        "inline": False
                    })
            
            # Price Guard Blocked Products (Warning Section)
            if summary.price_warnings:
                blocked_text = "\n".join([
                    f"🛡️ `{w.sku}` | **{w.name[:25]}**\nR$ {w.old_price:.2f} ➔ R$ {w.new_price:.2f} ({w.variation_percent:+.1f}%)"
                    for w in summary.price_warnings[:5]
                ])
                if len(summary.price_warnings) > 5:
                    blocked_text += f"\n... +{len(summary.price_warnings) - 5} mais"
                
                fields.append({
                    "name": "🛡️ ATENÇÃO: Preços Bloqueados (Price Guard)",
                    "value": blocked_text,
                    "inline": False
                })
            
            # Top Price Increases/Decreases
            if summary.top_price_increases:
                increase_text = "\n".join([
                    f"📈 `{c.sku}` | +{c.price_variation:.1f}% (R$ {c.old_price:.2f} → {c.new_price:.2f})"
                    for c in summary.top_price_increases[:3]
                ])
                fields.append({
                    "name": "📈 Maiores Aumentos",
                    "value": increase_text,
                    "inline": True
                })
            
            if summary.top_price_decreases:
                decrease_text = "\n".join([
                    f"📉 `{c.sku}` | {c.price_variation:.1f}% (R$ {c.old_price:.2f} → {c.new_price:.2f})"
                    for c in summary.top_price_decreases[:3]
                ])
                fields.append({
                    "name": "📉 Maiores Quedas",
                    "value": decrease_text,
                    "inline": True
                })
            
            # Ghost SKUs (if any)
            if summary.ghost_skus_zeroed:
                ghost_count = len(summary.ghost_skus_zeroed)
                ghost_preview = ", ".join(summary.ghost_skus_zeroed[:5])
                if ghost_count > 5:
                    ghost_preview += f"... +{ghost_count - 5}"
                
                fields.append({
                    "name": "👻 SKUs Zerados (Ghost)",
                    "value": f"**{ghost_count}** produtos\n{ghost_preview}",
                    "inline": False
                })
            
            # Errors (if any)
            if summary.errors:
                error_text = "\n".join(f"• {e}" for e in summary.errors[:3])
                if len(summary.errors) > 3:
                    error_text += f"\n... +{len(summary.errors) - 3} erros"
                
                fields.append({
                    "name": "❌ Erros",
                    "value": error_text,
                    "inline": False
                })
            
            # Build embed
            embed = {
                "title": f"📦 Sync Report - AquaFlora",
                "description": description,
                "color": color,
                "fields": fields,
                "thumbnail": {
                    "url": AQUAFLORA_LOGO
                },
                "footer": {
                    "text": f"AquaFlora Stock Sync • Python Edition • {summary.total_synced} sincronizados",
                    "icon_url": AQUAFLORA_LOGO
                },
                "timestamp": summary.timestamp.isoformat(),
            }
            
            response = self._client.post(
                self.discord_url,
                json={"embeds": [embed]},
            )
            
            if response.status_code in (200, 204):
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(f"Discord notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
    
    def _send_telegram(self, summary: SyncSummary):
        """Send Telegram message."""
        try:
            emoji = "✅" if summary.success else "❌"
            
            message = f"""
{emoji} *Sync Report - AquaFlora*

📊 Processados: {summary.total_parsed}
✨ Novos: {summary.new_products}
🔄 Atualizados: {summary.full_updates + summary.fast_updates}
⏭️ Ignorados: {summary.skipped}
"""
            
            if summary.price_warnings:
                message += f"\n🛡️ Bloqueados: {len(summary.price_warnings)}"
            
            if summary.ghost_skus_zeroed:
                message += f"\n👻 Zerados: {len(summary.ghost_skus_zeroed)}"
            
            if summary.errors:
                message += f"\n❌ Erros: {len(summary.errors)}"
            
            response = self._client.post(
                self.telegram_url,
                json={
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
            
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
            else:
                logger.warning(f"Telegram notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    def send_alert(self, title: str, message: str, is_error: bool = False):
        """Send a simple alert message."""
        if self.discord_url:
            try:
                embed = {
                    "title": title,
                    "description": message,
                    "color": COLOR_ERROR if is_error else COLOR_SUCCESS,
                    "thumbnail": {"url": AQUAFLORA_LOGO},
                }
                self._client.post(self.discord_url, json={"embeds": [embed]})
            except Exception as e:
                logger.error(f"Failed to send Discord alert: {e}")
    
    def close(self):
        """Close HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
