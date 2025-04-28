import os
import docx
from PyPDF2 import PdfReader
from ftp_utils import read_txt, read_docx, read_pdf, download_ftp_images
from ocr_utils import extract_text_from_images

def normalize_text(text):
    """
    Нормализует текст: приводит к нижнему регистру и убирает лишние пробелы.
    """
    return " ".join(text.lower().split())

def search_document(directory, query_text):
    """
    Ищет совпадения текста в файлах указанной директории.
    """
    matches = []
    normalized_query = normalize_text(query_text)

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)

            # Извлечение текста из файлов
            if file.endswith('.txt'):
                content = read_txt(file_path)
            elif file.endswith('.docx'):
                content = read_docx(file_path)
            elif file.endswith('.pdf'):
                content = read_pdf(file_path)
            else:
                continue

            # Нормализация текста файла
            normalized_content = normalize_text(content)

            # Логирование для отладки
            print(f"[DEBUG] Извлеченный текст из OCR: '{normalized_query}'")
            print(f"[DEBUG] Извлеченный текст из файла {file_path}: '{normalized_content}'")

            # Проверка на полное или частичное совпадение
            if normalized_query in normalized_content:
                matches.append(file_path)
            elif any(word in normalized_content for word in normalized_query.split()):
                matches.append(file_path)

    return matches

def search_text_in_ftp_images(user_text):
    image_paths = download_ftp_images()
    ftp_text = extract_text_from_images(image_paths)

    matches = []
    for line in ftp_text.split('\n'):
        if user_text.lower() in line.lower():
            matches.append(line)

    return matches