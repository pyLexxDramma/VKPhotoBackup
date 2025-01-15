import requests
import os
import json
from tqdm import tqdm
from datetime import datetime


def get_vk_photos(user_id, vk_token, count=5):
    url = "https://api.vk.com/method/photos.get"
    params = {
        "owner_id": user_id,
        "album_id": "profile",
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


def create_folder_if_not_exists(yandex_token, folder_name):
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {
        "Authorization": f"OAuth {yandex_token}"
    }

    # Проверим существование папки
    response = requests.get(f"{url}?path={folder_name}", headers=headers)
    if response.status_code == 404:
        # Папка не найдена, создадим её
        response = requests.put(f"{url}?path={folder_name}", headers=headers)
        if response.status_code != 201:
            print(f"Ошибка при создании папки: {response.status_code} - {response.text}")
    elif response.status_code != 200:
        print(f"Произошла ошибка при проверке существования папки: {response.status_code} - {response.text}")


def upload_to_yandex_disk(file_path, yandex_token, file_name):
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {
        "Authorization": f"OAuth {yandex_token}"
    }

    # Получаем ссылку для загрузки
    upload_url = f"{url}/upload?path={file_name}&overwrite=true"
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


def save_photos_info(photos_info, filename='photos_info.json'):
    with open(filename, 'w') as f:
        json.dump(photos_info, f, indent=4)


def main():
    user_id = input("Введите ID пользователя VK: ")
    vk_token = input("Введите токен VK: ")
    yandex_token = input("Введите токен Яндекс.Диска: ")
    count = int(input("Введите количество фотографий для сохранения (по умолчанию 5): ") or 5)

    # Создаем директорию для временных файлов, если она не существует
    if not os.path.exists('temp/temp'):
        os.makedirs('temp/temp')

    # Создаем папку на Яндекс.Диске
    folder_name = "backup_photos"
    create_folder_if_not_exists(yandex_token, folder_name)

    photos = get_vk_photos(user_id, vk_token, count)
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
        if upload_to_yandex_disk(file_path, yandex_token, f"{folder_name}/{file_name}"):
            photos_info.append({
                "file_name": file_name,
                "size": max_size['type']
            })
            print(f"Загружено: {file_name}")
        else:
            print(f"Не удалось загрузить: {file_name}")

        # Удаляем временный файл
        os.remove(file_path)

    save_photos_info(photos_info)
    print("Информация о фотографиях сохранена в photos_info.json")


if __name__ == "__main__":
    main()