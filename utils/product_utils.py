import os

from typing import Tuple
from sqlalchemy.orm import Query
from fastapi import Query
from math import ceil
from models import Product

def add_absolute_img_urls(products: list, base_url: str, field: str = "img_mini"):
    if os.getenv("ENV") == "production" and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)

    for product in products:
        if field == "img_mini" and product.img_mini:
            product.img_mini = [
                f"{base_url}/static/uploads/minify/{img}" for img in product.img_mini
            ]
        elif field == "images" and hasattr(product, "images") and product.images:
            for image in product.images:
                image.image_url = f"{base_url}/static/uploads/{image.image_url}"

def paginate_and_sort_products(
    query: Query,
    page: int = 1,
    limit: int = 12,
    sort_by: str = "name",
    order: str = "asc"
) -> Tuple[list, int, int]:
    order_field = getattr(Product, sort_by)
    if order == "desc":
        query = query.order_by(order_field.desc())
    else:
        query = query.order_by(order_field.asc())

    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()
    pages = ceil(total / limit)
    return products, total, pages