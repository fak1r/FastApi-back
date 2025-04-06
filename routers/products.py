import gspread
import pandas as pd
import models, schemas
from models import Product, ProductLine, ProductImage, Producer 
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from database import get_db
from typing import List, Optional
from utils.limiter import limiter
import re

# Создаём router для продуктов
router = APIRouter(prefix="/products", tags=["Products"])

# Подключение к Google Sheets через Service Account
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
@limiter.limit("10 per minute") 
@router.post("/upload_google")
async def upload_products_google(request: Request, sheet_url: str, db: Session = Depends(get_db)):
    try:
        # Загружаем Google Sheet в DataFrame
        df = get_google_sheet(sheet_url)

        # Столбцы, не относящиеся к деталям
        base_columns = {
            "Наименование", "Цена", "Img", "Img_mini", "is_favorite", "Описание", "product_line"
        }

        # Загружаем все текущие продукты из БД
        existing_products = db.query(Product).all()
        existing_products_dict = {p.name: p for p in existing_products}

        products_to_add = []
        products_to_update = []
        images_to_add = []
        sheet_product_names = set(df["Наименование"])

        for _, row in df.iterrows():
            # Получаем линейку по имени
            product_line = db.query(ProductLine).filter(
                ProductLine.name.ilike(row["product_line"])
            ).first()
            if not product_line:
                raise HTTPException(
                    status_code=400,
                    detail=f"Линейка '{row['product_line']}' не найдена в базе."
                )

            # Всё, что не входит в базовые поля — это детали (динамичные поля)
            details = {
                key: row[key]
                for key in df.columns
                if key not in base_columns
            }

            # Разделяем список изображений по запятой
            images = row.get("Img", "").split(",")
            images = [img.strip() for img in images if img.strip()]

            # Обработка миниатюры (как массив строк)
            img_mini_raw = row.get("Img_mini", "")
            img_mini = [img.strip() for img in img_mini_raw.split(",") if img.strip()]
            if not img_mini:
                img_mini = None

            # Проверяем, есть ли уже такой продукт
            existing_product = next(
                (
                    p for p in existing_products
                    if p.name.strip().lower() == row["Наименование"].strip().lower()
                ),
                None
            )

            if existing_product:
                # Обновляем только если что-то изменилось
                updated = False

                new_description = (
                    str(row["Описание"]).strip()
                    if pd.notna(row["Описание"]) else None
                )
                new_price = float(row["Цена"])
                new_favorite = (
                    str(row["is_favorite"]).strip().lower() in ["true", "TRUE"]
                )

                if existing_product.description != new_description:
                    existing_product.description = new_description
                    updated = True

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

                if updated:
                    products_to_update.append(existing_product)

                # Проверяем, изменились ли изображения
                existing_image_urls = {img.image_url for img in existing_product.images}
                if set(images) != existing_image_urls:
                    # Удаляем старые изображения
                    db.query(ProductImage).filter(
                        ProductImage.product_id == existing_product.id
                    ).delete()

                    # Добавляем новые
                    for img in images:
                        images_to_add.append(
                            ProductImage(product_id=existing_product.id, image_url=img)
                        )

            else:
                # Новый продукт
                product = Product(
                    name=str(row["Наименование"]).strip(),
                    description=(
                        str(row["Описание"]).strip()
                        if pd.notna(row["Описание"]) else None
                    ),
                    price=float(row["Цена"]),
                    product_line_id=product_line.id,
                    favorite=(
                        str(row["is_favorite"]).strip().lower() in ["true", "TRUE"]
                    ),
                    details=details,
                    img_mini=img_mini,
                    rating=0.0
                )

                products_to_add.append(product)

                # Связываем изображения с продуктом
                for img in images:
                    images_to_add.append(
                        ProductImage(product=product, image_url=img)
                    )

        # Удаляем те продукты, которых нет в таблице
        products_to_delete = [
            p for p in existing_products
            if p.name.strip().lower() not in {
                n.strip().lower() for n in sheet_product_names
            }
        ]

        for product in products_to_delete:
            db.delete(product)

        # Сохраняем изменения
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

@limiter.limit("10 per minute")
@router.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(request: Request, db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return categories

@limiter.limit("10 per minute")
@router.get("/producers", response_model=List[schemas.ProducerResponse])
def get_producers(request: Request, db: Session = Depends(get_db)):
    producers = db.query(models.Producer).all()
    return producers

@limiter.limit("10 per minute")
@router.get("/product_lines", response_model=List[schemas.ProductLineResponse])
def get_product_lines(request: Request, db: Session = Depends(get_db)):
    product_lines = db.query(models.ProductLine).all()
    return product_lines

@limiter.limit("30 per minute")
@router.get("/", response_model=List[schemas.ProductPreview])
def get_products(
    request: Request,
    db: Session = Depends(get_db),
    category_id: int = None,
    producer_id: int = None,
    product_line_id: int = None,
    min_price: float = None,
    max_price: float = None,
    favorite: bool = None,
    sort_by: str = Query(None, regex="^(price|name)$"),
    order: str = Query("asc", regex="^(asc|desc)$")
):
    query = db.query(Product)

    if category_id:
        producers_in_category = db.query(Producer.id).filter(
            Producer.category_id == category_id
        ).subquery()
        product_lines_in_category = db.query(ProductLine.id).filter(
            ProductLine.producer_id.in_(producers_in_category)
        ).subquery()
        query = query.filter(Product.product_line_id.in_(product_lines_in_category))

    if producer_id:
        product_lines_in_producer = db.query(ProductLine.id).filter(
            ProductLine.producer_id == producer_id
        ).subquery()
        query = query.filter(Product.product_line_id.in_(product_lines_in_producer))

    if product_line_id:
        query = query.filter(Product.product_line_id == product_line_id)

    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)

    if favorite is not None:
        query = query.filter(Product.favorite == favorite)

    if sort_by:
        order_func = getattr(Product, sort_by)
        if order == "desc":
            order_func = order_func.desc()
        query = query.order_by(order_func)

    products = query.all()

    # Преобразуем относительные пути миниатюр в абсолютные
    base_url = str(request.base_url).rstrip("/")
    for product in products:
        if product.img_mini:
            product.img_mini = [
                f"{base_url}/static/uploads/minify/{mini}" for mini in product.img_mini
            ]

    return products