from decimal import Decimal

from main import export_to_csv_lite
from src.sync import WooSyncManager


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"update": [{"id": 1001}]}


class _FakeWooApi:
    def __init__(self):
        self.posts = []

    def post(self, endpoint, payload):
        self.posts.append((endpoint, payload))
        return _FakeResponse()


class _FailedResponse:
    status_code = 500

    def json(self):
        return {"message": "failure"}


class _FailedWooApi(_FakeWooApi):
    def post(self, endpoint, payload):
        self.posts.append((endpoint, payload))
        return _FailedResponse()


def test_lite_csv_exports_only_sku_price_and_stock(sample_enriched_product, tmp_path):
    output = export_to_csv_lite([sample_enriched_product], tmp_path)

    lines = output.read_text(encoding="utf-8").splitlines()

    assert lines[0] == "SKU,Regular price,Stock"
    assert lines[1] == "12345,289.90,10"


def test_lite_api_payload_does_not_send_content_fields(populated_database, sample_enriched_product):
    product = sample_enriched_product.model_copy(
        update={"price": Decimal("299.90"), "stock": 8}
    )
    fake_api = _FakeWooApi()
    syncer = WooSyncManager(
        woo_url="https://example.test",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        lite_mode=True,
        dry_run=False,
    )
    syncer.wcapi = fake_api

    summary = syncer.sync_products([product], populated_database)

    assert summary.success is True
    assert summary.fast_updates == 1
    assert fake_api.posts[0][0] == "products/batch"

    update_payload = fake_api.posts[0][1]["update"][0]
    assert update_payload == {
        "id": 1001,
        "regular_price": "299.90",
        "stock_quantity": 8,
        "manage_stock": True,
        "stock_status": "instock",
    }

    forbidden_fields = {
        "name",
        "description",
        "short_description",
        "categories",
        "tags",
        "attributes",
        "images",
    }
    assert forbidden_fields.isdisjoint(update_payload)


def test_lite_mode_ignores_ghost_zeroing(populated_database, sample_enriched_product):
    populated_database.save_sync_result("P-PET-BEBEDOURO-PAI", 2002, "x", "x", 100)
    product = sample_enriched_product.model_copy(
        update={"price": Decimal("299.90"), "stock": 8}
    )
    fake_api = _FakeWooApi()
    syncer = WooSyncManager(
        woo_url="https://example.test",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        lite_mode=True,
        dry_run=False,
    )
    syncer.wcapi = fake_api

    summary = syncer.sync_products(
        [product],
        populated_database,
        zero_ghost_stock=True,
    )

    assert summary.success is True
    assert summary.ghost_skus_zeroed == []
    assert len(fake_api.posts) == 1
    assert fake_api.posts[0][1]["update"][0]["id"] == 1001


def test_failed_batch_does_not_mark_product_as_synced(populated_database, sample_enriched_product):
    product = sample_enriched_product.model_copy(
        update={"price": Decimal("299.90"), "stock": 8}
    )
    old_record = populated_database.get_record(product.sku)
    syncer = WooSyncManager(
        woo_url="https://example.test",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        lite_mode=True,
        dry_run=False,
    )
    syncer.wcapi = _FailedWooApi()

    summary = syncer.sync_products([product], populated_database)
    new_record = populated_database.get_record(product.sku)

    assert summary.success is False
    assert summary.fast_updates == 0
    assert new_record.last_hash_fast == old_record.last_hash_fast
    assert new_record.last_price == old_record.last_price


def test_ghost_zeroing_skips_synthetic_parent_skus(temp_database):
    temp_database.save_sync_result("P-PET-BEBEDOURO-PAI", 2002, "x", "x", 100)
    temp_database.save_sync_result("SKU-GHOST", 2003, "x", "x", 100)
    fake_api = _FakeWooApi()
    syncer = WooSyncManager(
        woo_url="https://example.test",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        lite_mode=False,
        dry_run=False,
    )
    syncer.wcapi = fake_api

    summary = syncer.sync_products(
        [],
        temp_database,
        zero_ghost_stock=True,
    )

    assert summary.success is True
    assert summary.ghost_skus_zeroed == ["SKU-GHOST"]
    assert len(fake_api.posts) == 1
    assert fake_api.posts[0][1] == {
        "update": [
            {
                "id": 2003,
                "stock_quantity": 0,
                "status": "draft",
            }
        ]
    }
