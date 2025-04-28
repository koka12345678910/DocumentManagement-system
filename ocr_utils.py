import easyocr

def ocr_process_image(image_path):
    """
    Извлекает текст из изображения с помощью OCR.
    """
    reader = easyocr.Reader(['en', 'ru'])
    results = reader.readtext(image_path, detail=0)
    extracted_text = " ".join(results)
    print(f"[DEBUG] Извлеченный текст из OCR: {extracted_text}")
    return extracted_text

def extract_text_from_image(image_path):
    reader = easyocr.Reader(['en', 'ru'])
    result = reader.readtext(image_path, detail=0)
    return ' '.join(result)

def extract_text_from_images(image_paths):
    all_text = ''
    for path in image_paths:
        text = extract_text_from_image(path)
        all_text += text + '\n'
    return all_text