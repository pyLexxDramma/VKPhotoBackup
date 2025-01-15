import requests
import os
import json
from tqdm import tqdm
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Настройки для Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_vk_photos(user_id, vk_token, album_id='profile', count=5):
    url = "https://api.vk.com/method/photos.get"
    params = {
        "owner_id": user_id,
        "album_id": album_id,
        "count": count,
        "extended": 1,
        "photo_sizes": 1,
        "access_token": vk_token,
        "v": "5.131"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['response']['items']
    else:
        print(f"Ошибка при получении фотографий: {response.status_code} - {response.text}")
        return []

def upload_to_yandex_disk(file_path, yandex_token, file_name):
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {
        "Authorization": f"OAuth {yandex_token}"
    }

    # Создаем папку, если она не существует
    folder_path = "backup_photos"
    requests.put(f"{url}/mkdir?path={folder_path}", headers=headers)

    # Получаем ссылку для загрузки
    upload_url = f"{url}/upload?path={folder_path}/{file_name}&overwrite=true"
    response = requests.get(upload_url, headers=headers)

    if response.status_code == 200:
        upload_url = response.json().get("href")
        if upload_url:
            with open(file_path, 'rb') as file:
                upload_response = requests.put(upload_url, files={'file': file})
                upload_response.raise_for_status()  # Проверка на ошибки
                return upload_response.status_code == 201
    else:
        print(f"Ошибка при получении ссылки для загрузки: {response.status_code} - {response.text}")

    return False


class MediaFileUpload:
    pass


def upload_to_google_drive(file_path, file_name):
    creds = None
    # Проверяем, есть ли сохраненные учетные данные
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # Если нет учетных данных, запрашиваем их у пользователя
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Сохраняем учетные данные для следующего запуска
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)

    # Загружаем файл на Google Drive
    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Файл загружен на Google Drive с ID: {file.get('id')}")

def save_photos_info(photos_info, filename='photos_info.json'):
    formatted_info = [{"file_name": photo["file_name"], "size": photo["size"]} for photo in photos_info]
    with open(filename, 'w') as f:
        json.dump(formatted_info, f, indent=4)

def main():
    user_id = input("Введите ID пользователя VK: ")
    vk_token = input("Введите токен VK: ")
    yandex_token = input("Введите токен Яндекс.Диска: ")
    album_id = input("Введите ID альбома (по умолчанию 'profile'): ") or 'profile'
    count = int(input("Введите количество фотографий для сохранения (по умолчанию 5): ") or 5)

    # Создаем директорию для временных файлов, если она не существует
    if not os.path.exists('temp'):
        os.makedirs('temp')

    photos = get_vk_photos(user_id, vk_token, album_id, count)
    photos_info = []

    print("Загрузка фотографий:")
    for photo in tqdm(photos):
        max_size = max(photo['sizes'], key=lambda x: x['width'] * x['height'])

        # Проверяем наличие лайков или используем дату загрузки
        likes_count = photo.get('likes', {}).get('count', 0)
        if likes_count > 0:
            file_name = f"{likes_count}.jpg"
        else:
            upload_date = datetime.fromtimestamp(photo['date']).strftime('%Y-%m-%d_%H-%M-%S')
            file_name = f"{upload_date}.jpg"

        file_path = f"temp/{file_name}"

        # Скачиваем фото
        photo_url = max_size['url']
        photo_response = requests.get(photo_url)
        with open(file_path, 'wb') as f:
            f.write(photo_response.content)

        # Загружаем на Яндекс.Диск
        if upload_to_yandex_disk(file_path, yandex_token, file_name):
            photos_info.append({
                "file_name": file_name,
                "size": max_size['type']  # Здесь можно указать нужный размер
            })
            print(f"Загружено на Яндекс.Диск: {file_name}")
        else:
            print(f"Не удалось загрузить на Яндекс.Диск: {file_name}")

        # Загружаем на Google Drive
        upload_to_google_drive(file_path, file_name)

        # Удаляем временный файл
        os.remove(file_path)

    save_photos_info(photos_info)
    print("Информация о фотографиях сохранена в photos_info.json")

if __name__ == "__main__":
    main()
