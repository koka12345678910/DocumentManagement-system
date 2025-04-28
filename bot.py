import os
import time
import requests
import json
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from config import TOKEN, FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, DOWNLOAD_PATH, DOWNLOAD_FILE
from ocr_utils import ocr_process_image
from ftp_utils import connect_ftp, download_file, list_files, upload_file
from search_utils import search_document
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
# Глобальная переменная для хранения последнего обработанного update_id
last_update_id = None
greeted_users = set()

def get_updates():
    """
    Получает новые сообщения от Telegram API.
    """
    global last_update_id
    url = f"{BASE_URL}/getUpdates"
    params = {'offset': last_update_id + 1} if last_update_id else {}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        updates = response.json()

        if 'result' in updates:
            for update in updates['result']:
                handle_update(update)
                last_update_id = update['update_id']

    except Exception as e:
        print(f"[ERROR] Ошибка при получении обновлений: {e}")

def send_message(chat_id, text, reply_markup=None):
    """
    Отправляет сообщение пользователю через Telegram API.
    """
    print(f"[INFO] Отправка сообщения пользователю: {text}")
    url = f"{BASE_URL}/sendMessage"
    data = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup.to_dict())
    response = requests.post(url, data=data)
    print(f"[INFO] Ответ от Telegram API на отправку сообщения: {response.status_code}, {response.text}")

def send_persistent_keyboard(chat_id):
    """
    Отправляет постоянную клавиатуру пользователю.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["📂 Показать все файлы", "🗂 Список файлов на сервере"],  # Добавьте новую кнопку здесь
        ],
        resize_keyboard=True,
        one_time_keyboard=False  # Клавиатура остается на экране
    )
    send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

def send_inline_keyboard(chat_id):
    """
    Отправляет inline-клавиатуру с кнопками.
    """
    buttons = [
        [InlineKeyboardButton("📂 Показать список файлов", callback_data="show_files")],
        [InlineKeyboardButton("🗂 Список файлов на сервере", callback_data="list_files")]  # Новая кнопка
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    send_message(chat_id, "Нажмите кнопку ниже для взаимодействия с файлами:", reply_markup=keyboard)

def handle_update(update):
    """
    Обрабатывает входящие обновления.
    """
    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']

        if 'photo' in message:
            file_id = message['photo'][-1]['file_id']
            handle_image(chat_id, file_id)
        elif 'document' in message:
            file_id = message['document']['file_id']
            handle_document(chat_id, file_id, message['document']['file_name'])
        elif 'text' in message:
            user_text = message['text']
            if user_text == "/start":
                if chat_id not in greeted_users:
                    send_message(chat_id, "Привет! Отправьте мне изображение или документ для поиска.")
                    send_persistent_keyboard(chat_id)
                    send_inline_keyboard(chat_id)
                    save_user(chat_id)  # Сохраняем пользователя, чтобы повторно не отправлять сообщение
                else:
                    send_message(chat_id, "С возвращением! Клавиатура уже активна.")
            elif user_text == "📂 Показать все файлы":
                show_files(chat_id)
            else:
                handle_text(chat_id, user_text)
        else:
            send_message(chat_id, "Пожалуйста, отправьте изображение, файл или текст.")
    elif 'callback_query' in update:
        handle_callback_query(update['callback_query'])

def handle_text(chat_id, user_text):
    """
    Обрабатывает текстовое сообщение, ищет совпадения на FTP-сервере по содержимому и именам файлов.
    """
    try:
        print(f"[INFO] Получено текстовое сообщение: {user_text}")

        # Подключение к FTP
        print(f"[INFO] Подключение к FTP серверу: {FTP_HOST}")
        ftp = connect_ftp(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS)
        remote_files = list_files(ftp, '/upload')
        print(f"[INFO] Список файлов на FTP сервере: {remote_files}")

        # Проверка совпадений по именам файлов
        matched_files_by_name = [
            remote_file for remote_file in remote_files if user_text.lower() in remote_file.lower()
        ]
        print(f"[INFO] Файлы с совпадением в имени: {matched_files_by_name}")

        # Скачивание всех файлов с FTP
        local_dir = f"{DOWNLOAD_PATH}/upload"
        os.makedirs(local_dir, exist_ok=True)
        print(f"[INFO] Локальная директория для файлов: {local_dir}")
        for remote_file in remote_files:
            local_file_path = f"{local_dir}/{os.path.basename(remote_file)}"
            print(f"[INFO] Скачивание файла с FTP: {remote_file} -> {local_file_path}")
            download_file(ftp, remote_file, local_file_path)

        # Поиск совпадений по содержимому
        print(f"[INFO] Запуск поиска совпадений по тексту...")
        matches_by_content = search_document(local_dir, user_text)

        # Уникальные совпадения по имени и содержимому
        all_matches = set(matched_files_by_name)
        all_matches.update(f"/upload/{os.path.basename(match)}" for match in matches_by_content)

        # Отправка совпадающих файлов
        if all_matches:
            for match in all_matches:
                send_file(chat_id, ftp, match)
        else:
            send_message(chat_id, "Совпадений не найдено.")
            print(f"[INFO] Совпадений не найдено.")

    except Exception as e:
        print(f"[ERROR] Ошибка при обработке текстового сообщения: {e}")
        send_message(chat_id, "Произошла ошибка при обработке вашего текста.")

def handle_callback_query(callback_query):
    """
    Обрабатывает нажатия на inline-кнопки.
    """
    chat_id = callback_query['message']['chat']['id']
    callback_data = callback_query['data']

    if callback_data == "show_files":
        show_files(chat_id)
    elif callback_data == "list_files":  # Новый обработчик для кнопки "Список файлов"
        handle_list_files_button(chat_id)

def handle_list_files_button(chat_id):
    """
    Обрабатывает нажатие кнопки для показа списка файлов на FTP-сервере.
    """
    try:
        print(f"[INFO] Подключение к FTP серверу для показа файлов: {FTP_HOST}")
        ftp = connect_ftp(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS)
        remote_files = list_files(ftp, '/upload')
        ftp.quit()

        if remote_files:
            files_list = "\n".join(remote_files)
            send_message(chat_id, f"Список файлов на сервере:\n\n{files_list}")
            print(f"[INFO] Список файлов отправлен пользователю: {files_list}")
        else:
            send_message(chat_id, "На сервере нет файлов.")
            print("[INFO] На сервере нет файлов.")
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке кнопки списка файлов: {e}")
        send_message(chat_id, "Произошла ошибка при получении списка файлов.")

def show_files(chat_id):
    """
    Получает и отправляет список файлов с FTP-сервера.
    """
    try:
        print(f"[INFO] Подключение к FTP серверу: {FTP_HOST}")
        ftp = connect_ftp(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS)
        remote_files = list_files(ftp, '/upload')
        ftp.quit()

        if remote_files:
            files_list = "\n".join(remote_files)
            send_message(chat_id, f"Список файлов на сервере:\n\n{files_list}")
        else:
            send_message(chat_id, "На сервере нет файлов.")
    except Exception as e:
        print(f"[ERROR] Ошибка при получении списка файлов: {e}")
        send_message(chat_id, "Произошла ошибка при получении списка файлов.")

def is_first_interaction(chat_id):
    """
    Проверяет, является ли это первая интеракция с пользователем.
    """
    return chat_id not in greeted_users

def save_user(chat_id):
    """
    Сохраняет пользователя в глобальный список.
    """
    greeted_users.add(chat_id)

def send_file(chat_id, ftp, remote_file):
    """
    Отправляет файл пользователю, предварительно скачав его с FTP-сервера.
    """
    local_temp_path = f"{DOWNLOAD_PATH}/{os.path.basename(remote_file)}"

    try:
        # Скачиваем файл с FTP
        print(f"[INFO] Скачивание файла {remote_file} с FTP на {local_temp_path}")
        with open(local_temp_path, 'wb') as f:
            ftp.retrbinary(f"RETR {remote_file}", f.write)

        # Отправляем файл пользователю через Telegram API
        print(f"[INFO] Отправка файла пользователю: {local_temp_path}")
        url = f"{BASE_URL}/sendDocument"
        with open(local_temp_path, 'rb') as f:
            response = requests.post(url, data={'chat_id': chat_id}, files={'document': f})

        if response.status_code == 200:
            print(f"[INFO] Файл {remote_file} успешно отправлен пользователю.")
        else:
            print(f"[ERROR] Ошибка при отправке файла: {response.status_code}, {response.text}")

    except Exception as e:
        print(f"[ERROR] Ошибка при отправке файла {remote_file}: {e}")

    finally:
        # Удаляем временный файл
        if os.path.exists(local_temp_path):
            os.remove(local_temp_path)

def handle_image(chat_id, file_id):
    """
    Обрабатывает изображение, выполняет OCR, ищет совпадения на FTP-сервере.
    """
    try:
        print(f"[INFO] Получение информации о файле с file_id: {file_id}")
        file_info = requests.get(f"{BASE_URL}/getFile", params={"file_id": file_id}).json()
        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        local_image_path = f"{DOWNLOAD_PATH}/{file_id}.jpg"

        # Скачиваем изображение
        print(f"[INFO] Скачивание изображения по URL: {file_url}")
        with open(local_image_path, 'wb') as f:
            f.write(requests.get(file_url).content)
        print(f"[INFO] Изображение сохранено в: {local_image_path}")

        # OCR обработка
        print(f"[INFO] Запуск OCR обработки изображения: {local_image_path}")
        extracted_text = ocr_process_image(local_image_path)

        # Если OCR не нашёл текст, отправляем сообщение
        if not extracted_text.strip():
            send_message(chat_id, "Пришлите фотографию файла.")
            return

        print(f"[INFO] Извлеченный текст: {extracted_text}")



        # Подключение к FTP и поиск
        print(f"[INFO] Подключение к FTP серверу: {FTP_HOST}")
        ftp = connect_ftp(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS)
        remote_files = list_files(ftp, '/upload')
        print(f"[INFO] Список файлов на FTP сервере: {remote_files}")

        # Скачивание файлов с FTP
        local_dir = f"{DOWNLOAD_PATH}/uploads"
        os.makedirs(local_dir, exist_ok=True)
        print(f"[INFO] Локальная директория для файлов: {local_dir}")
        for remote_file in remote_files:
            local_file_path = f"{local_dir}/{os.path.basename(remote_file)}"
            print(f"[INFO] Скачивание файла с FTP: {remote_file} -> {local_file_path}")
            download_file(ftp, remote_file, local_file_path)

        # Поиск совпадений
        print(f"[INFO] Запуск поиска совпадений по тексту...")
        matches = search_document(local_dir, extracted_text)

        if matches:
            # Отправляем файлы с совпадениями
            for match in matches:
                # Преобразуем локальный путь в путь на FTP
                remote_file = f"/upload/{os.path.basename(match)}"
                send_file(chat_id, ftp, remote_file)
        else:
            send_message(chat_id, "Совпадение не найдено.")
            print(f"[INFO] Совпадений не найдено.")

    except Exception as e:
        print(f"[ERROR] Ошибка при обработке изображения: {e}")
        send_message(chat_id, "Произошла ошибка при обработке вашего файла.")

def handle_document(chat_id, file_id, file_name):
    """
    Обрабатывает документ, загружая его на FTP-сервер.
    """
    try:
        print(f"[INFO] Получение информации о документе с file_id: {file_id}")
        file_info = requests.get(f"{BASE_URL}/getFile", params={"file_id": file_id}).json()

        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        local_file_path = f"{DOWNLOAD_FILE}/{file_name}"

        # Скачиваем документ
        print(f"[INFO] Скачивание документа по URL: {file_url}")
        response = requests.get(file_url)
        response.raise_for_status()

        with open(local_file_path, 'wb') as f:
            f.write(response.content)
        print(f"[INFO] Документ сохранен в: {local_file_path}")

        # Подключение к FTP и загрузка файла
        print(f"[INFO] Подключение к FTP серверу: {FTP_HOST}")
        ftp = connect_ftp(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS)
        remote_file_path = f"/upload/{file_name}"

        try:
            upload_file(ftp, local_file_path, remote_file_path)
            send_message(chat_id, f"✅ Файл *{file_name}* успешно загружен на сервер.")
            print(f"[INFO] Файл {file_name} успешно загружен на сервер.")
        except Exception as upload_error:
            print(f"[WARN] Ошибка при upload_file: {upload_error}")
            try:
                # Проверим, появился ли файл несмотря на ошибку
                files_list = ftp.nlst("/upload/")
                if file_name in files_list:
                    send_message(chat_id, f"⚠ Файл *{file_name}* загружен, но сервер вернул ошибку:\n`{upload_error}`")
                    print(f"[INFO] Файл загружен, но возникла ошибка: {upload_error}")
                else:
                    raise upload_error  # если файл не загрузился — пробросим
            except Exception as check_error:
                print(f"[ERROR] Ошибка при проверке наличия файла: {check_error}")

    except Exception as e:
        print(f"[ERROR] Общая ошибка при обработке документа: {e}")
        send_message(chat_id, "❌ Произошла ошибка при загрузке файла на сервер.")

if __name__ == "__main__":
    print("[INFO] Бот запущен и работает...")
    while True:
        try:
            get_updates()
            time.sleep(1)  # Добавляем небольшую задержку для предотвращения частых запросов
        except Exception as e:
            print(f"[ERROR] Общая ошибка в основной петле: {e}")
            time.sleep(5)