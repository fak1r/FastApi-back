import gspread
import pandas as pd
import models, schemas
from models import Product, ProductLine, ProductImage
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from database import get_db
from typing import List, Optional
from slowapi import Limiter
from schemas import ProductResponse
import re

limiter = Limiter(key_func=lambda: "global")  # Ограничения запросов

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
    df = get_google_sheet(sheet_url)
    base_columns = {"Наименование", "Цена", "Img", "is_favorite", "Описание", "product_line"}

    # Список товаров в БД
    existing_products = db.query(Product).all()
    existing_products_dict = {p.name: p for p in existing_products}

    products_to_add = []
    products_to_update = []
    images_to_add = []
    sheet_product_names = set(df["Наименование"])

    for _, row in df.iterrows():
      product_line = db.query(ProductLine).filter(ProductLine.name.ilike(row["product_line"])).first()
      if not product_line:
        raise HTTPException(status_code=400, detail=f"Линейка '{row['product_line']}' не найдена в базе.")

      details = {key: row[key] for key in df.columns if key not in base_columns}
      images = row.get("Img", "").split(",")  # Разделяем список картинок по запятой
      images = [img.strip() for img in images if img.strip()]  # Убираем пустые строки

      # Проверяем, есть ли товар в БД
      existing_product = next(
        (p for p in existing_products if p.name.strip().lower() == row["Наименование"].strip().lower()), None
      )

      if existing_product:
        # Проверяем, изменились ли данные
        if (
          existing_product.description != (str(row["Описание"]).strip() if pd.notna(row["Описание"]) else None)
          or existing_product.price != float(row["Цена"])
          or existing_product.favorite != (str(row["is_favorite"]).strip().lower() in ["true", "TRUE"])
          or existing_product.details != details
        ):
          # Если что-то изменилось – обновляем
          existing_product.description = str(row["Описание"]).strip() if pd.notna(row["Описание"]) else None
          existing_product.price = float(row["Цена"])
          existing_product.favorite = str(row["is_favorite"]).strip().lower() in ["true", "TRUE"]
          existing_product.details = details
          products_to_update.append(existing_product)

        # Проверяем, изменились ли картинки
        existing_image_urls = {img.image_url for img in existing_product.images}
        if set(images) != existing_image_urls:
          # Удаляем старые картинки и добавляем новые
          db.query(ProductImage).filter(ProductImage.product_id == existing_product.id).delete()
          for img in images:
            images_to_add.append(ProductImage(product_id=existing_product.id, image_url=img))
      else:
        # Если товара нет – добавляем
        product = Product(
          name=str(row["Наименование"]).strip(),
          description=str(row["Описание"]).strip() if pd.notna(row["Описание"]) else None,
          price=float(row["Цена"]),
          product_line_id=product_line.id,
          favorite=str(row["is_favorite"]).strip().lower() in ["true", "TRUE"],
          details=details
        )
        products_to_add.append(product)

        # Добавляем картинки к новому товару
        for img in images:
          images_to_add.append(ProductImage(product=product, image_url=img))

    # Удаляем только те товары, которые есть в БД, но отсутствуют в Google Sheets
    products_to_delete = [
      p for p in existing_products if p.name.strip().lower() not in {n.strip().lower() for n in sheet_product_names}
    ]

    for product in products_to_delete:
      db.delete(product)

    # Сохраняем изменения
    db.bulk_save_objects(products_to_update)
    db.add_all(products_to_add)
    db.add_all(images_to_add)
    db.commit()

    return {
      "message": f"{len(products_to_add)} новых продуктов добавлено, {len(products_to_update)} обновлено, {len(products_to_delete)} удалено!"
    }

  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Ошибка обработки данных: {str(e)}")

@router.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(request: Request, db: Session = Depends(get_db)):
  categories = db.query(models.Category).all()
  return [schemas.CategoryResponse(id=c.id, name=c.name, producers=[]) for c in categories]

@limiter.limit("10 per minute")
@router.get("/producers", response_model=List[schemas.ProducerResponse])
def get_producers(request: Request, db: Session = Depends(get_db)):
  producers = db.query(models.Producer).all()
  return [
    schemas.ProducerResponse(id=p.id, name=p.name, category_id=p.category_id, product_lines=[])
    for p in producers
  ]

@limiter.limit("10 per minute")
@router.get("/product_lines", response_model=List[schemas.ProductLineResponse])
def get_product_lines(request: Request, db: Session = Depends(get_db)):
  product_lines = db.query(models.ProductLine).all()
  return [
    schemas.ProductLineResponse(id=pl.id, name=pl.name, producer_id=pl.producer_id, products=[])
    for pl in product_lines
  ]

@limiter.limit("30 per minute")
@router.get("/", response_model=list[ProductResponse])
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
    producers_in_category = db.query(Producer.id).filter(Producer.category_id == category_id).subquery()
    product_lines_in_category = db.query(ProductLine.id).filter(ProductLine.producer_id.in_(producers_in_category)).subquery()
    query = query.filter(Product.product_line_id.in_(product_lines_in_category))

  if producer_id:
    product_lines_in_producer = db.query(ProductLine.id).filter(ProductLine.producer_id == producer_id).subquery()
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

  # Формируем полный URL для изображений
  base_url = str(request.base_url).rstrip("/")
  for product in products:
    for image in product.images:
      image.image_url = f"{base_url}/static/uploads/{image.image_url}"

  return products