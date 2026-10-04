"""Circuit breakers for the CLI's optional destructive reconciliation."""

import pytest
from types import SimpleNamespace

import main
from src.models import SyncSummary

from main import should_zero_ghost_stock


@pytest.mark.parametrize("overrides", [
    {"requested": False}, {"teste_mode": True},
    {"product_count": 50}, {"product_count": 89}, {"product_count": 0},
    {"mapped_site_products": 0}, {"filtered_out_count": 1},
    {"enrichment_error_count": 1},
])
def test_partial_or_failed_inventory_never_requests_zeroing(overrides):
    inputs = dict(requested=True, teste_mode=False, product_count=100, mapped_site_products=100)
    inputs.update(overrides)
    assert should_zero_ghost_stock(**inputs) is False


def test_explicit_request_with_sufficient_inventory_passes_the_count_guard():
    assert should_zero_ghost_stock(
        requested=True, teste_mode=False, product_count=90, mapped_site_products=100,
    ) is True


def test_partial_cli_export_does_not_forward_the_destructive_option(
    monkeypatch, tmp_path, sample_raw_product, sample_enriched_product,
):
    """Exercise orchestration, not just the guard's return value."""
    monkeypatch.setattr(main, "settings", SimpleNamespace(
        dry_run=True, sync_enabled=True, woo_configured=True,
        db_path=tmp_path / "synthetic.db", output_dir=tmp_path,
        woo_url="https://example.test", woo_consumer_key="", woo_consumer_secret="",
        price_guard_max_variation=40, zero_ghost_stock=True,
        discord_webhook_configured=False, backup_configured=False,
    ))
    monkeypatch.setattr(main, "AthosParser", lambda: SimpleNamespace(
        parse_file=lambda _: [sample_raw_product],
    ))
    monkeypatch.setattr(main, "ProductEnricher", lambda: SimpleNamespace(
        enrich=lambda _: sample_enriched_product,
    ))
    monkeypatch.setattr(main, "_load_exclusion_config", lambda: {})
    monkeypatch.setattr(main, "_filter_excluded_products", lambda products, _: (products, {}))
    monkeypatch.setattr(main, "generate_weight_outlier_report", lambda *_: None)
    monkeypatch.setattr(main, "ProductDatabase", lambda _: SimpleNamespace(
        get_stats=lambda: {"total_products": 100, "synced_to_woo": 100},
        get_site_products_count=lambda: 100, close=lambda: None,
    ))
    forwarded = []

    def fake_sync(products, db, *, zero_ghost_stock):
        forwarded.append(zero_ghost_stock)
        return SyncSummary(total_parsed=len(products), success=True)

    monkeypatch.setattr(main, "WooSyncManager", lambda **_: SimpleNamespace(sync_products=fake_sync))
    monkeypatch.setattr(main, "export_to_csv_full", lambda *_: tmp_path / "preview.csv")
    monkeypatch.setattr(main, "export_dry_run_review_files", lambda *_, **__: tmp_path)
    monkeypatch.setattr(main, "print_report", lambda _: None)
    result = main.process_file(tmp_path / "synthetic.csv", dry_run=True)
    assert result.success is True
    assert forwarded == [False]
    assert not (tmp_path / "synthetic.db").exists()
