"""Seed a small, deterministic local product catalogue.

This script intentionally creates products only. Reviews are accepted through the
ingestion service once that service exists, so this never bypasses its deduplication
or job semantics.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from backend.app.config import get_settings
from backend.app.db.models import Product
from backend.app.db.session import make_engine


DEMO_PRODUCTS = (
    ("demo-laptop-aurora-14", "Aurora 14", "Laptops", "Northstar"),
    ("demo-laptop-summit-16", "Summit 16", "Laptops", "Northstar"),
    ("demo-laptop-trail-13", "Trail 13", "Laptops", None),
)


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        with engine.begin() as connection:
            for external_id, name, category, brand in DEMO_PRODUCTS:
                statement = insert(Product).values(
                    id=uuid5(NAMESPACE_URL, f"review-tag-generator/{external_id}"),
                    source="demo",
                    external_product_id=external_id,
                    name=name,
                    category=category,
                    brand=brand,
                )
                connection.execute(
                    statement.on_conflict_do_nothing(
                        index_elements=[Product.source, Product.external_product_id],
                        index_where=Product.external_product_id.is_not(None),
                    )
                )
        print(f"Ensured {len(DEMO_PRODUCTS)} demo products.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
