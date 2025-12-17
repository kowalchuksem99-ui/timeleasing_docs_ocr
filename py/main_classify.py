import time
from multiprocessing import Process
from classification import PREDICT
from py.FILE_HANDLERS.relocation import extract_archives_in_folder, move_files
import sys
import os
from threading import Thread
import threading  # already using Thread, we re-use here

# Кэш последнего известного состояния каждой папки
#   True  → папка доступна/существует
#   False → недоступна (для сетевых) или не удалось создать (для локальных)
_FOLDER_STATUS: dict[str, bool] = {}
_STATUS_LOCK = threading.Lock()
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))
import os
print("Текущий рабочий каталог:", os.getcwd())
print("Переменные среды:")
for k in ["HOMEPATH", "USERPROFILE", "USERNAME", "HOMEDRIVE", "PATH"]:
    print(k, "=", os.environ.get(k))

# Список директорий менеджеров
DIRS_MANAGERS = [
    r"Z:\\"
]

# Путь до директории, из которой скрипт ведет работу
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Директории для классификации
WORD_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'word')
PDF_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'pdf')
IMG_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'img')
EXCEL_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'excel')

def is_network_path(path):
    # Для Windows: сетевые пути начинаются с двойного обратного слеша
    return path.startswith(r"\\") or path.startswith("//")

def check_folders(path: str) -> bool:
    """
    • Логирует ТОЛЬКО если состояние папки изменилось
      (появилась/создана/пропала).
    • Возвращает `True`, если папка в итоге доступна, иначе `False`.
    """
    def _log(msg: str) -> None:
        # Если когда-нибудь решите перейти на модуль logging —
        # замените ТОЛЬКО эту одну функцию.
        print(msg)

    with _STATUS_LOCK:
        prev_alive = _FOLDER_STATUS.get(path)

        # --- Проверяем текущее состояние ------------------------------------
        alive_now = os.path.exists(path)

        # --- Сетевые пути ----------------------------------------------------
        if is_network_path(path):
            if prev_alive is None or prev_alive != alive_now:
                if alive_now:
                    _log(f"🌐 Сетевая папка снова доступна → {path}")
                else:
                    _log(f"⚠ Сетевая папка недоступна или не смонтирована → {path}")
            _FOLDER_STATUS[path] = alive_now
            return alive_now

        # --- Локальные пути --------------------------------------------------
        if not alive_now:
            try:
                os.makedirs(path, exist_ok=True)
                _log(f"📁 Локальная папка создана → {path}")
                alive_now = True
            except Exception as exc:
                _log(f"⚠ Не удалось создать {path}: {exc}")
                alive_now = False
        else:
            # Если увидели папку впервые, всё-таки сообщим об этом один раз
            if prev_alive is None:
                _log(f"📁 Локальная папка уже существует → {path}")

        _FOLDER_STATUS[path] = alive_now
        return alive_now

def delete_empty_dirs(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                print(f"Удалена пустая папка: {dirpath}")
            except Exception as e:
                print(f"Ошибка при удалении {dirpath}: {e}")

def process_files():
    prev_state = {}  # {classify_dir: set(file_list)}
    known_dirs = set()
    while True:
        try:
            for base_dir in DIRS_MANAGERS:
                if not check_folders(base_dir):
                    continue
                # Получаем все подпапки первого уровня
                subfolders = [
                    os.path.join(base_dir, name)
                    for name in os.listdir(base_dir)
                    if os.path.isdir(os.path.join(base_dir, name))
                ]
                # Для каждой подпапки ищем "На классификацию"
                for work_dir in subfolders:
                    classify_dir = os.path.join(work_dir, "На классификацию")
                    if not os.path.exists(classify_dir):
                        continue
                    # Лог новых появившихся директорий
                    if classify_dir not in known_dirs:
                        print(f"▶ Найдена новая папка для классификации: {classify_dir}")
                        known_dirs.add(classify_dir)
                    try:
                        files = set(os.listdir(classify_dir))
                    except Exception as e:
                        print(f"Ошибка чтения {classify_dir}: {e}")
                        continue
                    prev_files = prev_state.get(classify_dir, set())
                    # Только если содержимое изменилось
                    if files != prev_files:
                        if files:
                            print(f"📄 {classify_dir}: {sorted(files)}")
                        else:
                            print(f"🗑 {classify_dir} теперь пуста")
                        prev_state[classify_dir] = files
                    # Если появились новые файлы — обрабатываем
                    if files:
                        extract_archives_in_folder(classify_dir)
                        move_files(
                            classify_dir,
                            word_dir=WORD_PREDICT_DIR,
                            pdf_dir=PDF_PREDICT_DIR,
                            img_dir=IMG_PREDICT_DIR,
                            excel_dir=EXCEL_PREDICT_DIR,
                            manager_word=os.path.join(work_dir, 'Исходники', 'word'),
                            manager_pdf=os.path.join(work_dir, 'Исходники', 'pdf'),
                            manager_img=os.path.join(work_dir, 'Исходники', 'img'),
                            manager_excel=os.path.join(work_dir, 'Исходники', 'excel')
                        )
        except Exception as e:
            print(f"Файл используется или другая ошибка: {e}")
            for dir in DIRS_MANAGERS:
                check_folders(dir)
        time.sleep(5)  # разумная задержка


def classify_files():
    while True:
        try:
            start_time = time.time()
            timeout = 1
            while time.time() - start_time < timeout:
                WORD_FILES_PREDICT = os.listdir(WORD_PREDICT_DIR)
                PDF_FILES_PREDICT = os.listdir(PDF_PREDICT_DIR)
                IMG_FILES_PREDICT = os.listdir(IMG_PREDICT_DIR)
                EXCEL_FILES_PREDICT = os.listdir(EXCEL_PREDICT_DIR)

                if WORD_FILES_PREDICT or PDF_FILES_PREDICT or IMG_FILES_PREDICT or EXCEL_FILES_PREDICT:
                    print("Запускаю PREDICT")
                    MODEL = (r"C:\Users\kovalchuk\PycharmProjects\DOCS_ANALYZE\py\CORE_VECTOR\30.04.2025"
                             r"\core_pipeline.joblib")
                    PREDICT(
                        WORD_FILES_PREDICT, WORD_PREDICT_DIR,
                        PDF_FILES_PREDICT, PDF_PREDICT_DIR,
                        EXCEL_FILES_PREDICT, EXCEL_PREDICT_DIR,
                        IMG_FILES_PREDICT, IMG_PREDICT_DIR,
                        MODEL
                    )
                time.sleep(1)
        except Exception as e:
            print(f"Процесса классификации оборвлся: {e}")


if __name__ == "__main__":
    # Проверяем наличие директорий менеджеров
    for directs in DIRS_MANAGERS:
        check_folders(directs)
    # Проверяем наличие целевых директорий для классификации
    check_folders(WORD_PREDICT_DIR)
    check_folders(PDF_PREDICT_DIR)
    check_folders(IMG_PREDICT_DIR)
    check_folders(EXCEL_PREDICT_DIR)

    # Создаем два процесса для параллельной работы
    t1 = Thread(target=process_files)
    t2 = Thread(target=classify_files)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
