import os
import gspread
from dotenv import load_dotenv

load_dotenv()

SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_URL = os.getenv("SHEET_URL")
IMAGES_FILE = os.path.join(os.path.dirname(__file__), "grouped_images.txt")
start_row = 2

if not SHEET_URL:
    raise ValueError("⛔ Переменная SHEET_URL не найдена в .env")

# Авторизация
gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
sheet = gc.open_by_url(SHEET_URL).sheet1

# Читаем строки из файла
with open(IMAGES_FILE, encoding="utf-8") as f:
    image_lines = [line.strip() for line in f if line.strip()]

# Диапазон
end_row = start_row + len(image_lines) - 1
cell_range = f"F{start_row}:F{end_row}"
cell_list = sheet.range(cell_range)

# Запись в ячейки
for i, cell in enumerate(cell_list):
    cell.value = image_lines[i]

sheet.update_cells(cell_list)

print(f"✅ {len(image_lines)} строк с изображениями записано в колонку F, начиная с F{start_row}")
