import os, platform
import shutil
import patoolib
import time
import sys
import re
import errno

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

def _is_busy(exc: BaseException) -> bool:
    # Windows: winerror 32 (занят другим процессом)
    if getattr(exc, "winerror", None) == 32:
        return True
    # POSIX: занято/нет доступа
    err = getattr(exc, "errno", None)
    return err in {errno.EBUSY, errno.EACCES}

def safe_move(src: str, dst: str, *, retries: int = 20, base_delay: float = 0.4) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            # Пытаемся атомарно (одна ФС)
            os.replace(src, dst)
            return
        except OSError as e:
            if e.errno == errno.EXDEV:
                # Разные файловые системы/маунты → копируем и удаляем
                shutil.copy2(src, dst)
                os.remove(src)
                return
            if _is_busy(e):
                time.sleep(base_delay * (1.5 ** (attempt - 1)))
                continue
            raise
    raise PermissionError(f"[BUSY] Не удалось переместить после {retries} попыток: {src} -> {dst}")


def safe_copy(src: str, dst: str, *, retries: int = 20, base_delay: float = 0.4) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            shutil.copy2(src, dst)
            return
        except (PermissionError, OSError) as e:
            if _is_busy(e):
                time.sleep(base_delay * (1.5 ** (attempt - 1)))
                continue
            raise
    raise PermissionError(f"[BUSY] Не удалось скопировать после {retries} попыток: {src} -> {dst}")

def safe_remove(path: str, *, retries: int = 15, base_delay: float = 0.3) -> None:
    for attempt in range(1, retries + 1):
        try:
            os.remove(path)
            return
        except (PermissionError, OSError) as e:
            if _is_busy(e):
                time.sleep(base_delay * (1.5 ** (attempt - 1)))
                continue
            if not os.path.exists(path):
                return
            raise
    # не падаем — просто оставим предупреждение
    print(f"[WARN] Не удалось удалить (занят): {path}")

def safe_rmtree(path: str, *, retries: int = 10, base_delay: float = 0.3) -> None:
    for attempt in range(1, retries + 1):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            return
        except (PermissionError, OSError) as e:
            if _is_busy(e):
                time.sleep(base_delay * (1.5 ** (attempt - 1)))
                continue
            if not os.path.exists(path):
                return
            raise
    print(f"[WARN] Не удалось удалить папку (занята): {path}")


def check_folders(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Папка {folder_path} создана")
    else:
        print(f"Папка {folder_path} уже существует")


def extract_archive(archive_path, dest_dir, attempts=3):
    os.makedirs(dest_dir, exist_ok=True)
    temp_dir = os.path.join(dest_dir, "_temp_unpacking")

    for i in range(attempts):
        try:
            # Создаём временную папку для извлечения
            os.makedirs(temp_dir, exist_ok=True)
            patoolib.extract_archive(archive_path, outdir=temp_dir, verbosity=-1)

            # Перемещаем все файлы из всех подпапок в dest_dir
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    src_path = os.path.join(root, file)
                    dst_path = os.path.join(dest_dir, file)

                    # Если файл с таким именем уже существует — переименовываем
                    if os.path.exists(dst_path):
                        base, ext = os.path.splitext(file)
                        counter = 1
                        while os.path.exists(dst_path):
                            new_name = f"{base}_{counter}{ext}"
                            dst_path = os.path.join(dest_dir, new_name)
                            counter += 1

                    safe_move(src_path, dst_path)

            safe_rmtree(temp_dir)
            safe_remove(archive_path)
            return True
        except Exception as e:
            print(f"Попытка {i + 1} не удалась: {e}")
            time.sleep(1)
            safe_rmtree(temp_dir)

    return False


def extract_archives_in_folder(folder):
    # Запускаем бесконечный цикл, который будет выполняться, пока не будет найдено ни одного архива
    while True:
        # Флаг для отслеживания наличия найденных архивов в текущем обходе
        found_archive = False
        # Рекурсивный обход директории с помощью os.walk, который проходит по всем подкаталогам и файлам
        for root, dirs, files in os.walk(folder):
            # Перебираем каждый файл в текущей директории
            for file in files:
                # Получаем расширение файла, преобразованное к нижнему регистру
                extension = file.split('.')[-1].lower()
                # Проверяем, является ли файл архивом по расширению
                if extension in ['rar', 'zip', '7z']:
                    # Устанавливаем флаг, что архив найден
                    found_archive = True
                    # Формируем полный путь к архиву, объединяя текущую директорию и имя файла
                    archive_path = os.path.join(root, file)
                    print(f"Обнаружен архив: {archive_path}")

                    # Пытаемся извлечь архив с помощью функции extract_archive
                    # Передаём полный путь к архиву и директорию, куда следует извлечь файлы
                    if extract_archive(archive_path, root):
                        print(f"Архив {archive_path} извлечен успешно.")
                    else:
                        print(f"Ошибка извлечения архива {archive_path}. Пропускаем его.")

        # Если ни один архив не был найден на текущем обходе, значит процесс завершён
        if not found_archive:
            break


def move_files(
    path_source, word_dir, pdf_dir, img_dir, excel_dir,
    manager_word, manager_pdf, manager_excel, manager_img
):
    for root, dirs, files in os.walk(path_source):
        for file in files:
            src_file = os.path.join(root, file)
            extension = file.split('.')[-1].lower()
            # Определяем родительскую папку (например, "890201974267")
            try:
                top_subfolder = re.search(r'([^\\/]+)[\\/][^\\/]+$', root).group(1)
            except Exception:
                top_subfolder = "unknown"

            new_file_name = f"({top_subfolder})_{file}"

            if extension in ["xlsx", "xls"]:
                dst = os.path.join(excel_dir, new_file_name)
                manager_dst = os.path.join(manager_excel, new_file_name)
                check_folders(excel_dir)
                check_folders(manager_excel)
                print("Перемещаем Excel в:", os.path.abspath(dst))
                safe_move(src_file, dst)
                print("Копируем Excel в:", os.path.abspath(manager_dst))
                safe_copy(dst, manager_dst)

            elif extension in ["docx", "doc", "odt", "rtf"]:
                dst = os.path.join(word_dir, new_file_name)
                manager_dst = os.path.join(manager_word, new_file_name)
                check_folders(word_dir)
                check_folders(manager_word)
                print("Перемещаем Word в:", os.path.abspath(dst))
                safe_move(src_file, dst)
                print("Копируем Word в:", os.path.abspath(manager_dst))
                safe_copy(dst, manager_dst)

            elif extension == "pdf":
                dst = os.path.join(pdf_dir, new_file_name)
                manager_dst = os.path.join(manager_pdf, new_file_name)
                check_folders(pdf_dir)
                check_folders(manager_pdf)
                print("Перемещаем PDF в:", os.path.abspath(dst))
                safe_move(src_file, dst)
                print("Копируем PDF в:", os.path.abspath(manager_dst))
                safe_copy(dst, manager_dst)

            elif extension in ["png", "jpeg", "jpg", "jfif", "tiff", "bmp"]:
                dst = os.path.join(img_dir, new_file_name)
                manager_dst = os.path.join(manager_img, new_file_name)
                check_folders(img_dir)
                check_folders(manager_img)
                print("Перемещаем изображение в:", os.path.abspath(dst))
                safe_move(src_file, dst)
                print("Копируем изображение в:", os.path.abspath(manager_dst))
                safe_copy(dst, manager_dst)

            else:
                print(f"Расширение файла {file} не обрабатывается.")
                try:
                    # Определяем путь к папке "Готовые" внутри той же подпапки
                    current_base = os.path.dirname(root)  # <- это путь типа Z:\890201974267
                    ready_dir = os.path.join(current_base, "Готовые")
                    check_folders(ready_dir)
                    new_name = f"Пока не умеем обрабатывать такие файлы_{file}"
                    new_src_file = os.path.join(root, new_name)
                    os.rename(src_file, new_src_file)
                    print(f"Перемещаем в Готовые: {ready_dir}")
                    shutil.move(new_src_file, ready_dir)
                except Exception as e:
                    print(f"Не удалось переместить {file} в папку Готовые: {e}")



def clear_directory(directory):
    # Обход по файлам
    for item in os.listdir(directory):
        # Путь до файла
        item_path = os.path.join(directory, item)
        try:
            # Это файл ?
            if os.path.isfile(item_path) or os.path.islink(item_path):
                # Удаляем
                os.unlink(item_path)
            # Это директория ?
            elif os.path.isdir(item_path):
                # Удаляем
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"Ошибка при удалении {item_path}: {e}")

