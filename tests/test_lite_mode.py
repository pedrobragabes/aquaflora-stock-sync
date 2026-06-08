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
