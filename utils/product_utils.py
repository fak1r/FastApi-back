def add_absolute_img_urls(products: list, base_url: str):
    for product in products:
        if product.img_mini:
            product.img_mini = [
                f"{base_url}/static/uploads/minify/{img}" for img in product.img_mini
            ]