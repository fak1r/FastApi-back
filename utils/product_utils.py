import os

from typing import Tuple
from sqlalchemy.orm import Query
from fastapi import Query
from math import ceil
from models import Product

ENV = os.getenv("ENV", "development")

if ENV == "production":
    SITE_URL = os.getenv("SITE_URL", "https://zampol.ru")
else:
    SITE_URL = "http://localhost:8000" 

def add_absolute_img_urls(products: list, field: str = "img_mini"):
    for product in products:
        if field == "img_mini" and product.img_mini:
            product.img_mini = [
                f"{SITE_URL}/static/uploads/minify/{img}" for img in product.img_mini
            ]
        elif field == "images" and hasattr(product, "images") and product.images:
            for image in product.images:
                image.image_url = f"{SITE_URL}/static/uploads/{image.image_url}"

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