from ftplib import FTP
import docx
from PyPDF2 import PdfReader
def connect_ftp(host, port, user, password):
    """
    Подключается к FTP-серверу.
    """
    ftp = FTP()
    ftp.connect(host, port)
    ftp.login(user, password)
    return ftp

def list_files(ftp, directory):
    """
    Возвращает список файлов в указанной директории на FTP-сервере.
    """
    ftp.cwd(directory)
    return ftp.nlst()

def download_file(ftp, remote_file, local_path):
    """
    Скачивает файл с FTP-сервера.
    """
    with open(local_path, 'wb') as f:
        ftp.retrbinary(f"RETR {remote_file}", f.write)

def download_ftp_images(temp_folder='ftp_images'):
    os.makedirs(temp_folder, exist_ok=True)

    image_files = [f for f in ftp.nlst() if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    downloaded_files = []

    for image_name in image_files:
        local_path = os.path.join(temp_folder, image_name)
        with open(local_path, 'wb') as f:
            ftp.retrbinary(f'RETR {image_name}', f.write)
        downloaded_files.append(local_path)

    ftp.quit()
    return downloaded_files

def upload_file(ftp, local_file, remote_file):
    """
    Загружает файл на FTP-сервер.
    """
    with open(local_file, 'rb') as f:
        ftp.storbinary(f"STOR {remote_file}", f)
        print(f"[INFO] Файл {local_file} успешно загружен на {remote_file}")

def read_txt(file_path):
    """
    Читает текст из TXT файла.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"[DEBUG] Текст из TXT файла {file_path}: '{content}'")
    return content

def read_docx(file_path):
    """
    Читает текст из DOCX файла.
    """
    doc = docx.Document(file_path)
    content = " ".join([paragraph.text for paragraph in doc.paragraphs])
    print(f"[DEBUG] Текст из DOCX файла {file_path}: '{content}'")
    return content

def read_pdf(file_path):
    """
    Читает текст из PDF файла.
    """
    reader = PdfReader(file_path)
    content = " ".join([page.extract_text() or "" for page in reader.pages])
    print(f"[DEBUG] Текст из PDF файла {file_path}: '{content}'")
    return content
