import gspread
from slugify import slugify

# Имя файла service account
SERVICE_ACCOUNT_FILE = "service_account.json"

# URL твоего Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1uNiNE9FbDrrWekhlZ4iyeXSUuTAFl5c3ta-Gx6F50G0/edit?gid=485629002#gid=485629002"

# Авторизация
gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
sheet = gc.open_by_url(SHEET_URL).sheet1

# Получаем все названия из столбца A (начиная с A2)
names = sheet.col_values(1)[1:]  # пропускаем заголовок A1
slugs = [slugify(name) for name in names]

# Записываем slug-и в столбец D, начиная с D2
cell_range = f"D2:D{len(slugs)+1}"
cell_list = sheet.range(cell_range)

for i, cell in enumerate(cell_list):
    cell.value = slugs[i]

# Сохраняем изменения
sheet.update_cells(cell_list)

print(f"✅ {len(slugs)} slug-ов записано в столбец D")