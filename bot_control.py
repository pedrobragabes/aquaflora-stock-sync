#!/usr/bin/env python3
"""
AquaFlora Stock Sync - Discord Bot Controller 2.0
Remote control and monitoring for stock sync via Discord commands.

Usage:
    python bot_control.py

Commands:
    !status       - Show sync status
    !forcar_agora - Force immediate sync
    !log          - Send last log file
    !produtos     - Show last 10 changed products
    !precos       - Show top price increases/decreases
    !whitelist    - Show whitelist stats
    !ajuda        - Show help menu
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("❌ py-cord not installed. Run: pip install py-cord")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

logger = logging.getLogger(__name__)

# AquaFlora branding
AQUAFLORA_LOGO = "https://aquafloragroshop.com.br/wp-content/uploads/2021/08/cropped-logo-aquaflora-agroshop-1.png"
COLOR_PRIMARY = 0x2ECC71  # Green
COLOR_INFO = 0x3498DB     # Blue
COLOR_WARNING = 0xF1C40F  # Yellow


# Global state
class BotState:
    sync_status: str = "Idle"
    last_sync: Optional[datetime] = None
    is_processing: bool = False


state = BotState()


def load_last_run_stats() -> Optional[dict]:
    """Load the last run stats from JSON file."""
    stats_path = Path("last_run_stats.json")
    if stats_path.exists():
        try:
            with open(stats_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load last_run_stats.json: {e}")
    return None


def create_bot() -> commands.Bot:
    """Create and configure the Discord bot."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        description="AquaFlora Stock Sync Controller 2.0"
    )
    
    @bot.event
    async def on_ready():
        """Called when bot is ready."""
        await bot.wait_until_ready()
        logger.info(f"🤖 Bot connected as {bot.user}")
        logger.info(f"📢 Serving {len(bot.guilds)} guilds")
        
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="estoque | !ajuda"
            )
        )
    
    # ==========================================================================
    # HELP COMMAND
    # ==========================================================================
    @bot.command(name="ajuda", aliases=["help_sync", "comandos", "menu"])
    async def help_cmd(ctx):
        """Show available commands with rich embed."""
        embed = discord.Embed(
            title="🤖 AquaFlora Stock Bot - Menu de Comandos",
            description="Controle e monitore a sincronização de estoque diretamente pelo Discord!",
            color=COLOR_PRIMARY
        )
        embed.set_thumbnail(url=AQUAFLORA_LOGO)
        
        embed.add_field(
            name="📊 **Informativos**",
            value=(
                "`!status` - Status atual do sistema\n"
                "`!whitelist` - Estatísticas da whitelist de SKUs\n"
                "`!log` - Envia o último arquivo de log"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 **Inteligência de Negócio**",
            value=(
                "`!produtos` - Últimos 10 produtos alterados\n"
                "`!precos` - Top 5 maiores altas e quedas de preço"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ **Ações**",
            value=(
                "`!forcar_agora` - Força sincronização imediata\n"
                "`!sync` - Alias para forcar_agora"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="AquaFlora Stock Sync • Bot 2.0",
            icon_url=AQUAFLORA_LOGO
        )
        
        await ctx.send(embed=embed)
    
    # ==========================================================================
    # STATUS COMMAND
    # ==========================================================================
    @bot.command(name="status")
    async def status_cmd(ctx):
        """Show current sync status with rich embed."""
        embed = discord.Embed(
            title="📦 AquaFlora Stock Sync - Status",
            color=COLOR_PRIMARY if state.sync_status == "Idle" else COLOR_WARNING
        )
        embed.set_thumbnail(url=AQUAFLORA_LOGO)
        
        embed.add_field(
            name="🔄 Status",
            value=f"**{state.sync_status}**",
            inline=True
        )
        
        embed.add_field(
            name="📅 Última Sync",
            value=state.last_sync.strftime("%d/%m %H:%M") if state.last_sync else "Nunca",
            inline=True
        )
        
        # Get database stats
        try:
            from src.database import ProductDatabase
            db = ProductDatabase(settings.db_path)
            stats = db.get_stats()
            site_count = db.get_site_products_count()
            db.close()
            
            embed.add_field(
                name="📊 Produtos no DB",
                value=f"**{stats['total_products']}**",
                inline=True
            )
            
            embed.add_field(
                name="🛡️ Whitelist",
                value=f"**{site_count}** mapeados",
                inline=True
            )
        except Exception as e:
            logger.debug(f"Could not get DB stats: {e}")
        
        # Load last run stats
        last_stats = load_last_run_stats()
        if last_stats:
            embed.add_field(
                name="📋 Última Execução",
                value=(
                    f"✨ Novos: **{last_stats.get('new_products', 0)}**\n"
                    f"🔄 Atualizados: **{last_stats.get('full_updates', 0) + last_stats.get('fast_updates', 0)}**\n"
                    f"⏭️ Ignorados: **{last_stats.get('skipped', 0)}**"
                ),
                inline=False
            )
        
        embed.set_footer(text="Use !ajuda para ver todos os comandos")
        
        await ctx.send(embed=embed)
    
    # ==========================================================================
    # WHITELIST COMMAND
    # ==========================================================================
    @bot.command(name="whitelist", aliases=["wl", "mapeados"])
    async def whitelist_cmd(ctx):
        """Show whitelist statistics."""
        embed = discord.Embed(
            title="📊 Status da Whitelist",
            description="SKUs mapeados do WooCommerce para sincronização segura",
            color=COLOR_INFO
        )
        embed.set_thumbnail(url=AQUAFLORA_LOGO)
        
        try:
            from src.database import ProductDatabase
            db = ProductDatabase(settings.db_path)
            stats = db.get_stats()
            site_count = db.get_site_products_count()
            db.close()
            
            total = stats.get('total_products', 0)
            on_site = site_count
            
            embed.add_field(
                name="🔢 Total de SKUs Mapeados",
                value=f"**{on_site:,}**",
                inline=True
            )
            
            embed.add_field(
                name="✅ Prontos para Sync",
                value=f"**{on_site:,}**",
                inline=True
            )
            
            embed.add_field(
                name="📁 Total no Banco",
                value=f"**{total:,}**",
                inline=True
            )
            
            # Calculate ghost potential
            ghost_potential = total - on_site if total > on_site else 0
            if ghost_potential > 0:
                embed.add_field(
                    name="👻 Produtos Ignorados (não no site)",
                    value=f"**{ghost_potential:,}**",
                    inline=False
                )
            
            embed.set_footer(text="Execute --map-site para atualizar a whitelist")
            
        except Exception as e:
            embed.add_field(
                name="❌ Erro",
                value=f"Não foi possível acessar o banco de dados: {str(e)[:100]}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    # ==========================================================================
    # PRODUCTS COMMAND (Last 10 Changes)
    # ==========================================================================
    @bot.command(name="produtos", aliases=["changes", "alterados"])
    async def produtos_cmd(ctx):
        """Show last 10 products that were changed."""
        last_stats = load_last_run_stats()
        
        if not last_stats or not last_stats.get('product_changes'):
            embed = discord.Embed(
                title="📋 Últimos Produtos Alterados",
                description="Nenhuma alteração registrada ainda.\nExecute uma sincronização primeiro!",
                color=COLOR_WARNING
            )
            embed.set_thumbnail(url=AQUAFLORA_LOGO)
            await ctx.send(embed=embed)
            return
        
        changes = last_stats.get('product_changes', [])[:10]
        
        embed = discord.Embed(
            title="📋 Últimos 10 Produtos Alterados",
            description=f"Da sincronização de {last_stats.get('timestamp', 'N/A')[:16]}",
            color=COLOR_INFO
        )
        embed.set_thumbnail(url=AQUAFLORA_LOGO)
        
        for change in changes:
            # Determine emoji
            change_type = change.get('change_type', 'updated')
            if change_type == 'new':
                emoji = "🆕"
            elif change.get('price_variation', 0) > 0:
                emoji = "📈"
            elif change.get('price_variation', 0) < 0:
                emoji = "📉"
            else:
                emoji = "➖"
            
            name = change.get('name', 'Sem nome')[:35]
            sku = change.get('sku', 'N/A')
            old_price = change.get('old_price')
            new_price = change.get('new_price', 0)
            variation = change.get('price_variation', 0)
            
            if old_price:
                value = f"R$ {old_price:.2f} ➔ R$ {new_price:.2f} ({variation:+.1f}%)"
            else:
                value = f"R$ {new_price:.2f} (NOVO)"
            
            embed.add_field(
                name=f"{emoji} `{sku}` | {name}",
                value=value,
                inline=False
            )
        
        total_changes = len(last_stats.get('product_changes', []))
        if total_changes > 10:
            embed.set_footer(text=f"Mostrando 10 de {total_changes} alterações")
        
        await ctx.send(embed=embed)
    
    # ==========================================================================
    # PRICES COMMAND (Top Increases/Decreases)
    # ==========================================================================
    @bot.command(name="precos", aliases=["prices", "variacoes"])
    async def precos_cmd(ctx):
        """Show top price increases and decreases."""
        last_stats = load_last_run_stats()
        
        if not last_stats or not last_stats.get('product_changes'):
            embed = discord.Embed(
                title="📈📉 Variações de Preço",
                description="Nenhuma alteração registrada ainda.\nExecute uma sincronização primeiro!",
                color=COLOR_WARNING
            )
            embed.set_thumbnail(url=AQUAFLORA_LOGO)
            await ctx.send(embed=embed)
            return
        
        changes = last_stats.get('product_changes', [])
        
        # Filter and sort
        increases = sorted(
            [c for c in changes if c.get('price_variation', 0) > 0],
            key=lambda x: x.get('price_variation', 0),
            reverse=True
        )[:5]
        
        decreases = sorted(
            [c for c in changes if c.get('price_variation', 0) < 0],
            key=lambda x: x.get('price_variation', 0)
        )[:5]
        
        embed = discord.Embed(
            title="📈📉 Variações de Preço",
            description=f"Da sincronização de {last_stats.get('timestamp', 'N/A')[:16]}",
            color=COLOR_INFO
        )
        embed.set_thumbnail(url=AQUAFLORA_LOGO)
        
        # Top Increases
        if increases:
            increase_text = "\n".join([
                f"📈 `{c.get('sku')}` | **+{c.get('price_variation', 0):.1f}%** (R$ {c.get('old_price', 0):.2f} → {c.get('new_price', 0):.2f})"
                for c in increases
            ])
            embed.add_field(
                name="🔺 Top 5 Maiores Aumentos",
                value=increase_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🔺 Top 5 Maiores Aumentos",
                value="Nenhum aumento registrado",
                inline=False
            )
        
        # Top Decreases
        if decreases:
            decrease_text = "\n".join([
                f"📉 `{c.get('sku')}` | **{c.get('price_variation', 0):.1f}%** (R$ {c.get('old_price', 0):.2f} → {c.get('new_price', 0):.2f})"
                for c in decreases
            ])
            embed.add_field(
                name="🔻 Top 5 Maiores Quedas",
                value=decrease_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🔻 Top 5 Maiores Quedas",
                value="Nenhuma queda registrada",
                inline=False
            )
        
        # Price warnings
        warnings = last_stats.get('price_warnings', [])
        if warnings:
            warning_text = "\n".join([
                f"🛡️ `{w.get('sku')}` | {w.get('variation_percent', 0):+.1f}% BLOQUEADO"
                for w in warnings[:3]
            ])
            if len(warnings) > 3:
                warning_text += f"\n... +{len(warnings) - 3} mais"
            
            embed.add_field(
                name="⚠️ Preços Bloqueados (Price Guard)",
                value=warning_text,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    # ==========================================================================
    # FORCE SYNC COMMAND
    # ==========================================================================
    @bot.command(name="forcar_agora", aliases=["sync", "forcar"])
    async def forcar_agora_cmd(ctx):
        """Force immediate sync."""
        if state.is_processing:
            await ctx.send("⚠️ Sincronização já em andamento! Aguarde...")
            return
        
        input_dir = settings.input_dir
        if not input_dir.exists():
            await ctx.send(f"📭 Diretório de entrada não existe: `{input_dir}`")
            return
            
        csv_files = list(input_dir.glob("*.csv"))
        
        if not csv_files:
            await ctx.send(f"📭 Nenhum arquivo CSV encontrado em `{input_dir}`")
            return
        
        latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
        
        await ctx.send(f"🚀 Iniciando sincronização...\n📁 Arquivo: `{latest_file.name}`")
        
        state.sync_status = "Processing"
        state.is_processing = True
        
        try:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None,
                _run_sync,
                latest_file
            )
            
            state.last_sync = datetime.now()
            state.sync_status = "Idle"
            
            # Build result embed
            color = 0x2ECC71 if summary.success else 0xE74C3C
            embed = discord.Embed(
                title="✅ Sync Concluído" if summary.success else "❌ Sync com Erros",
                color=color
            )
            embed.set_thumbnail(url=AQUAFLORA_LOGO)
            
            embed.add_field(name="📄 Parseados", value=str(summary.total_parsed), inline=True)
            embed.add_field(name="✨ Novos", value=str(summary.new_products), inline=True)
            embed.add_field(name="🔄 Atualizados", value=str(summary.full_updates + summary.fast_updates), inline=True)
            
            if summary.price_warnings:
                embed.add_field(
                    name="🛡️ Bloqueados",
                    value=str(len(summary.price_warnings)),
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            state.sync_status = "Error"
            logger.error(f"Sync error: {e}")
            await ctx.send(f"❌ Erro na sincronização: ```{str(e)[:500]}```")
        finally:
            state.is_processing = False
    
    # ==========================================================================
    # LOG COMMAND
    # ==========================================================================
    @bot.command(name="log", aliases=["logs"])
    async def log_cmd(ctx):
        """Send last log file."""
        log_dir = Path("./logs")
        
        if not log_dir.exists():
            await ctx.send("📭 Nenhum log encontrado")
            return
        
        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            await ctx.send("📭 Nenhum arquivo de log encontrado")
            return
        
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
        
        if latest_log.stat().st_size > 8 * 1024 * 1024:
            with open(latest_log, 'rb') as f:
                f.seek(-100 * 1024, 2)
                content = f.read().decode('utf-8', errors='ignore')
            
            await ctx.send(
                f"📋 Últimas linhas de `{latest_log.name}`:\n```\n{content[-1900:]}```"
            )
        else:
            await ctx.send(
                f"📋 Log: `{latest_log.name}`",
                file=discord.File(latest_log)
            )
    
    # ==========================================================================
    # ERROR HANDLER
    # ==========================================================================
    @bot.event
    async def on_command_error(ctx, error):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ Comando não encontrado. Use `!ajuda` para ver os comandos disponíveis.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"❌ Erro: {str(error)[:200]}")
    
    return bot


def _run_sync(filepath: Path):
    """Run sync in thread pool."""
    from main import process_file
    return process_file(filepath, dry_run=settings.dry_run, lite_mode=True)


def main():
    """Run the Discord bot."""
    if not settings.discord_bot_configured:
        print("❌ DISCORD_BOT_TOKEN não configurado no .env")
        print("   Configure a variável no arquivo .env e tente novamente.")
        sys.exit(1)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    bot = create_bot()
    
    print("🤖 Iniciando AquaFlora Stock Bot 2.0...")
    print("   Comandos: !ajuda, !status, !produtos, !precos, !whitelist")
    print("   Pressione Ctrl+C para parar")
    
    try:
        bot.run(settings.discord_bot_token)
    except discord.LoginFailure:
        print("❌ Token inválido! Verifique DISCORD_BOT_TOKEN no .env")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Bot encerrado")


if __name__ == "__main__":
    main()
