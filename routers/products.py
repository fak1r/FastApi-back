import gspread
import pandas as pd
import models, schemas
from models import Product, ProductLine, ProductImage, Producer, Category
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from database import get_db
from typing import List, Optional
from slugify import slugify
from math import ceil
from utils.product_utils import add_absolute_img_urls, paginate_and_sort_products
import re

# Создаём router для продуктов
router = APIRouter(prefix="/products", tags=["Products"])

SERVICE_ACCOUNT_FILE = "service_account.json"

def get_google_sheet(sheet_url: str):
    try:
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url).group(1)  # Извлекаем sheet_id из URL
        sheet = gspread.service_account(SERVICE_ACCOUNT_FILE).open_by_key(sheet_id).sheet1
        df = pd.DataFrame(sheet.get_all_values())
        df.columns = df.iloc[0]  # Устанавливаем заголовки
        return df[1:]  # Возвращаем данные без первой строки
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Google Sheets API: {str(e)}")

# Эндпоинт загрузки продуктов из Google Sheets
@router.post("/upload_google")
async def upload_products_google(sheet_url: str, db: Session = Depends(get_db)):
    try:
        df = get_google_sheet(sheet_url)

        # Всё что не относится к деталям
        base_columns = {
            "Наименование", "Цена", "Img", "Img_mini", "is_favorite", "product_line", 'slug', "full_name"
        }

        existing_products = db.query(Product).all()
        existing_products_dict = {p.name: p for p in existing_products}

        products_to_add = []
        products_to_update = []
        images_to_add = []
        sheet_product_names = set(df["Наименование"])
        seen_slugs = set()

        for _, row in df.iterrows():
            product_name = str(row["Наименование"]).strip()

            # Если есть повторы, добавляем индекс
            base_slug = slugify(product_name)
            new_slug = base_slug
            counter = 1
            while new_slug in seen_slugs:
                new_slug = f"{base_slug}-{counter}"
                counter += 1
            seen_slugs.add(new_slug)

            # Получаем или создаём линейку
            product_line_name = row["product_line"].strip()
            product_line = db.query(ProductLine).filter(
                ProductLine.name.ilike(product_line_name)
            ).first()

            if not product_line:
                product_line = ProductLine(
                    name=product_line_name,
                    slug=slugify(product_line_name)
                )
                db.add(product_line)
                db.flush()
            elif not product_line.slug:
                product_line.slug = slugify(product_line.name)
                db.add(product_line)
                db.flush()

            details = {
                key: row[key]
                for key in df.columns
                if key not in base_columns and pd.notna(row[key])
            }

            if "Описание" in row and pd.notna(row["Описание"]):
                details["Описание"] = str(row["Описание"]).strip()

            images = row.get("Img", "").split(",")
            images = [img.strip() for img in images if img.strip()]

            img_mini_raw = row.get("Img_mini", "")
            img_mini = [img.strip() for img in img_mini_raw.split(",") if img.strip()]
            if not img_mini:
                img_mini = None

            # Проверка существующего продукта
            existing_product = next(
                (
                    p for p in existing_products
                    if p.name.strip().lower() == product_name.lower()
                ),
                None
            )

            if existing_product:
                updated = False

                new_price = float(row["Цена"])
                new_favorite = (
                    str(row["is_favorite"]).strip().lower() in ["true", "TRUE"]
                )

                if existing_product.price != new_price:
                    existing_product.price = new_price
                    updated = True

                if existing_product.favorite != new_favorite:
                    existing_product.favorite = new_favorite
                    updated = True

                if existing_product.details != details:
                    existing_product.details = details
                    updated = True

                if existing_product.img_mini != img_mini:
                    existing_product.img_mini = img_mini
                    updated = True

                # Обновляем slug только если ИМЯ изменилось
                if existing_product.name.strip().lower() != product_name.lower():
                    base_slug = slugify(product_name)
                    new_slug = base_slug
                    counter = 1
                    while new_slug in seen_slugs:
                        new_slug = f"{base_slug}-{counter}"
                        counter += 1
                    seen_slugs.add(new_slug)

                    existing_product.slug = new_slug
                    updated = True

                if updated:
                    products_to_update.append(existing_product)

                # Обновляем изображения, если изменились
                existing_image_urls = {img.image_url for img in existing_product.images}
                if set(images) != existing_image_urls:
                    db.query(ProductImage).filter(
                        ProductImage.product_id == existing_product.id
                    ).delete()
                    for img in images:
                        images_to_add.append(
                            ProductImage(product_id=existing_product.id, image_url=img)
                        )

            else:
                product = Product(
                    name=product_name,
                    slug=new_slug,
                    price=float(row["Цена"]),
                    product_line_id=product_line.id,
                    favorite=(
                        str(row["is_favorite"]).strip().lower() in ["true", "TRUE"]
                    ),
                    details=details,
                    img_mini=img_mini,
                    rating=0.0,
                    full_name=row.get("full_name") 
                )

                products_to_add.append(product)

                for img in images:
                    images_to_add.append(
                        ProductImage(product=product, image_url=img)
                    )

        # Удаляем отсутствующие в таблице продукты
        products_to_delete = [
            p for p in existing_products
            if p.name.strip().lower() not in {
                n.strip().lower() for n in sheet_product_names
            }
        ]

        for product in products_to_delete:
            db.delete(product)

        db.bulk_save_objects(products_to_update)
        db.add_all(products_to_add)
        db.add_all(images_to_add)
        db.commit()

        return {
            "message": (
                f"{len(products_to_add)} новых продуктов добавлено, "
                f"{len(products_to_update)} обновлено, {len(products_to_delete)} удалено!"
            )
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка обработки данных: {str(e)}")

@router.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return categories

@router.get("/producers", response_model=List[schemas.ProducerResponse])
def get_producers(db: Session = Depends(get_db)):
    producers = db.query(models.Producer).all()
    return producers

@router.get("/product_lines", response_model=List[schemas.ProductLineResponse])
def get_product_lines(db: Session = Depends(get_db)):
    product_lines = db.query(models.ProductLine).all()
    return product_lines

@router.get("/popular", response_model=schemas.PaginatedProducts)
def get_popular_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    sort_by: str = Query("name", pattern="^(price|name)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Product)
        .join(ProductLine)
        .join(Producer)
        .join(Category)
        .filter(Product.favorite == True)
    )

    products, total, pages = paginate_and_sort_products(query, page, limit, sort_by, order)

    base_url = str(request.base_url).rstrip("/")
    add_absolute_img_urls(products, base_url)

    for product in products:
        category_slug = product.product_line.producer.category.slug
        producer_slug = product.product_line.producer.slug
        product.self = f"/{category_slug}/{producer_slug}/{product.slug}"

    return {
        "items": products,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


@router.get("/{category_slug}", response_model=schemas.PaginatedProducts)
def get_products_by_category_slug(
    request: Request,
    category_slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    sort_by: str = Query("name", pattern="^(price|name)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Product)
        .join(ProductLine)
        .join(Producer)
        .join(Category)
        .filter(Category.slug == category_slug)
    )

    products, total, pages = paginate_and_sort_products(query, page, limit, sort_by, order)

    base_url = str(request.base_url).rstrip("/")
    add_absolute_img_urls(products, base_url)

    for product in products:
        producer_slug = product.product_line.producer.slug
        product.self = f"/{category_slug}/{producer_slug}/{product.slug}"

    return {
        "items": products,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

@router.get("/{category_slug}/{producer_slug}", response_model=schemas.PaginatedProducts)
def get_products_by_producer_slug(
    request: Request,
    category_slug: str,
    producer_slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    sort_by: str = Query("name", pattern="^(price|name)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Product)
        .join(ProductLine)
        .join(Producer)
        .join(Category)
        .filter(
            Producer.slug == producer_slug,
            Category.slug == category_slug
        )
    )

    products, total, pages = paginate_and_sort_products(query, page, limit, sort_by, order)

    base_url = str(request.base_url).rstrip("/")
    add_absolute_img_urls(products, base_url)

    for product in products:
        product.self = f"/{category_slug}/{producer_slug}/{product.slug}"

    return {
        "items": products,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

@router.get("/{category_slug}/{producer_slug}/{product_slug}", response_model=schemas.ProductResponse)
def get_product_by_slug(
    category_slug: str,
    producer_slug: str,
    product_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    product = (
        db.query(Product)
        .join(ProductLine)
        .join(Producer)
        .join(Category)
        .filter(
            Product.slug == product_slug,
            Producer.slug == producer_slug,
            Category.slug == category_slug
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    base_url = str(request.base_url).rstrip("/")
    add_absolute_img_urls([product], base_url, field="images")

    return product