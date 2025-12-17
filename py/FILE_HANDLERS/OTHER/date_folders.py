import datetime
import sys
import os

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

path_folder = r"/py/CORE_VECTOR"


def TIME_FOLDERS(path):
    """
    Создает датированную директорию

    :param path: путь директории в котором необходимо создать новую датированную директорию
    :return new_time_folder: путь новой директории
    """

    # Получаем нынешнюю дату
    current_date = datetime.date.today().strftime('%d.%m.%Y')
    # Полный путь до новой директории
    new_time_folder = os.path.join(path, current_date)
    # Создаем новую директорию, если такой еще не существует
    os.makedirs(new_time_folder, exist_ok=True)

    return new_time_folder
