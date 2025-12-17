from __future__ import annotations

import os, platform, errno
import shutil
import sys
import time
from typing import Iterable
from date_extract import extraction

# ---------------------------------------------------------------------------
#  General helpers (без логики дат)
# ---------------------------------------------------------------------------

sys.path.append(os.path.join(os.path.dirname(__file__), "py"))

DEFAULT_PATH = os.environ.get("DEFAULT_PATH") or (
    r"Z:\\" if platform.system() == "Windows" else "/mnt/docs/"
)


def move_file_cross_disk(src: str, dst: str, retries: int = 20, base_delay: float = 0.4) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            # Попытка быстрой операции на одной ФС
            os.replace(src, dst)
            print(f"Файл успешно перемещён (rename): {src} -> {dst}")
            return

        except OSError as e:
            # Кросс-диск: копируем и удаляем исходник
            if getattr(e, "errno", None) == errno.EXDEV:
                try:
                    shutil.copy2(src, dst)
                    try:
                        os.remove(src)
                    except PermissionError as e_rm:
                        # «Файл занят» — подождём и повторим удаление
                        if getattr(e_rm, "winerror", None) == 32:
                            delay = base_delay * (1.5 ** (attempt - 1))
                            print(f"[BUSY-DEL] {src} занят, попытка {attempt}/{retries}, ждём {delay:.2f}s...")
                            time.sleep(delay)
                            continue
                        raise
                    print(f"Файл успешно перемещён (copy+remove): {src} -> {dst}")
                    return
                except (PermissionError, OSError) as e_cp:
                    # Если «занят» — подождём и повторим цикл
                    if getattr(e_cp, "winerror", None) == 32:
                        delay = base_delay * (1.5 ** (attempt - 1))
                        print(f"[BUSY-CP] {src} занят, попытка {attempt}/{retries}, ждём {delay:.2f}s...")
                        time.sleep(delay)
                        continue
                    raise

            # Windows-вариант «занят»: winerror 32
            if getattr(e, "winerror", None) == 32:
                delay = base_delay * (1.5 ** (attempt - 1))
                print(f"[BUSY] {src} занят, попытка {attempt}/{retries}, ждём {delay:.2f}s...")
                time.sleep(delay)
                continue

            # Прочие ошибки — пробрасываем
            raise

    print(f"[FAIL] Не удалось переместить после {retries} попыток: {src} -> {dst}")


def delete_from_source(surname: str, filename: str, extension: str) -> None:
    ext_map = {
        "word": ["docx", "doc", "docm"],
        "pdf": ["pdf"],
        "img": ["png", "jpeg", "jpg", "jfif", "tiff"],
        "excel": ["xlsx", "xls", "xlsm", "xlsb"],
    }

    for subfolder, exts in ext_map.items():
        if extension in exts:
            path = os.path.join(DEFAULT_PATH, surname, "Исходники", subfolder, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Удалён исходник из Исходники: {path}")
                except Exception as exc:
                    print(f"Не удалось удалить исходник {path}: {exc}")
            break


# ---------------------------------------------------------------------------
#  Main (логика дат полностью удалена)
# ---------------------------------------------------------------------------

def FILE_CLASS_RENAME(
    predict_data: Iterable[str],
    documents: Iterable[str],   # Оставлены для совместимости, не используются
    filenames: Iterable[str],   # Оставлены для совместимости, не используются
    class_list: Iterable[str],
    pdf_path: str,
    word_path: str,
    excel_path: str,
    img_path: str,
) -> None:

    for key, new_name in zip(predict_data, class_list):
        try:
            # Определяем расширение и ФИО
            extension = key.split(".")[-1].lower()
            surname = (
                key.split(")")[0][1:]
                if key.startswith("(") and ")" in key
                else key.split("_")[0].strip("()")
            )

            # Имя файла без даты
            file_uid = os.path.splitext(key)[0].split("_")[-1]
            new_filename = f"{new_name}_{file_uid}.{extension}"

            # Готовая папка
            ready_dir = os.path.join(DEFAULT_PATH, surname, "Готовые")
            os.makedirs(ready_dir, exist_ok=True)

            # Определяем, откуда брать исходный файл
            if extension in {"xlsx", "xls", "xlsm", "xlsb"}:
                src_file = os.path.join(excel_path, key)
            elif extension in {"docx", "doc", "docm"}:
                src_file = os.path.join(word_path, key)
            elif extension == "pdf":
                src_file = os.path.join(pdf_path, key)
            elif extension in {"png", "jpeg", "jpg", "jfif", "tiff"}:
                src_file = os.path.join(img_path, key)
            else:
                print(f"Неизвестное расширение файла {key}, пропускаю.")
                continue

            # Перемещаем файл и чистим Исходники
            dst_file = os.path.join(ready_dir, new_filename)
            move_file_cross_disk(src_file, dst_file)
            delete_from_source(surname, key, extension)

        except Exception as exc:
            print(f"Не удалось обработать файл {key}: {exc}")