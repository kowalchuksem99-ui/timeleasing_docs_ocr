#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMG_TEXT_EXTRACTOR: OCR для изображений с Excel-подобной обработкой ошибок.
- Валидируем изображение (Pillow verify/load).
- Успех: OCR -> LEGITIMAZE -> texts[file] = ...
- Ошибка: переименовать с префиксом (уникально) и переместить в Z:\<bucket>\Готовые.

Зависимости: Pillow, pytesseract, ваш LEGITIMAZE.
"""

import os
import re
import shutil
import sys
from typing import Dict
from PIL import Image, UnidentifiedImageError
import pytesseract
from py.TEXT_HANDLERS.lemma import LEGITIMAZE

# ================== КОНФИГ ==================
# Каталог базового назначения как в Excel-логике
DEFAULT_PATH = r"Z:\\"
ALLOWED_EXTS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}

# Укажи путь к tesseract.exe при необходимости (Windows)
if os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = os.environ.get(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

# ================== ХЕЛПЕРЫ ==================
def extract_bucket(file_name: str) -> str:
    """
    Извлекает "корзину" из имени файла, игнорируя префиксы 'Битый[_ren]_' / 'OCRFail_ren_'.
    Примеры: '(Иванов)_scan1.png' -> 'Иванов', 'Петров_акт_1.png' -> 'Петров'
    """
    base = os.path.basename(file_name)
    name_wo_ext = os.path.splitext(base)[0]
    name_wo_prefix = re.sub(r'^(?:Битый(?:_ren)?_|OCRFail_ren_)', '', name_wo_ext, flags=re.IGNORECASE)
    if name_wo_prefix.startswith('(') and ')' in name_wo_prefix:
        return name_wo_prefix[1:name_wo_prefix.index(')')]
    bucket = name_wo_prefix.split('_')[0].strip('() ')
    return bucket or "_"

def _unique_path(path: str) -> str:
    """Возвращает уникальный путь, если файл уже существует (добавляет счётчик)."""
    if not os.path.exists(path):
        return path
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    i = 1
    while True:
        cand = os.path.join(folder, f"{stem}_{i}{ext}")
        if not os.path.exists(cand):
            return cand
        i += 1

def move_to_ready(file_path: str, file_name: str, bucket: str = None) -> None:
    """
    Переносит файл в Z:\<bucket>\Готовые с гарантией уникального имени.
    """
    if bucket is None:
        bucket = extract_bucket(file_name)
    ready_dir = os.path.join(DEFAULT_PATH, bucket, "Готовые")
    os.makedirs(ready_dir, exist_ok=True)
    dst = _unique_path(os.path.join(ready_dir, file_name))
    try:
        shutil.move(file_path, dst)
        print(f"[MOVE] {file_name} -> {ready_dir}")
    except Exception as e:
        print(f"[MOVE:ERROR] {file_name}: {e}")

def _is_valid_image(path: str) -> bool:
    """True, если файл читается Pillow и декодируется."""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
        return True
    except (UnidentifiedImageError, OSError):
        return False

def _mark_and_move_broken(file_path: str, file_name: str, repos_dir: str, bucket: str, prefix: str) -> None:
    """
    Переименовать в <prefix><name> (уникально) в репозитории и затем переместить в Z:\<bucket>\Готовые.
    Поведение идентично Excel-кейсу.
    """
    folder = repos_dir
    broken_name = f"{prefix}{file_name}"
    broken_path = os.path.join(folder, broken_name)
    # уникальность внутри репозитория
    i = 1
    while os.path.exists(broken_path):
        broken_name = f"{prefix}{i}_{file_name}"
        broken_path = os.path.join(folder, broken_name)
        i += 1
    try:
        os.replace(file_path, broken_path)
    except Exception as e:
        print(f"[RENAME:ERROR] {file_name}: {e}")
        broken_name = file_name
        broken_path = file_path
    move_to_ready(broken_path, broken_name, bucket)

# ================== ОСНОВНАЯ ФУНКЦИЯ ==================
def IMAGE_TEXT_EXTRACTOR(file_names, image_repos) -> Dict[str, str]:
    """
    Извлекает текст из валидных img-файлов.
    Битые/ошибочные: переименовать с префиксом и переместить в Z:\<bucket>\Готовые.
    Возврат: {'имя файла': 'лемматизированный текст', ...}
    """
    texts: Dict[str, str] = {}
    for file in file_names:
        if "_ren_" in file:
            # Уже помечен ранее — пропускаем (ожидается, что он уже перемещён)
            continue

        ext = os.path.splitext(file)[1].lower()
        if ext and ext not in ALLOWED_EXTS:
            continue

        file_path = os.path.join(image_repos, str(file))
        bucket = extract_bucket(file)

        if not os.path.isfile(file_path):
            print(f"[MISS] {file_path}")
            continue

        # Валидация перед OCR
        if not _is_valid_image(file_path):
            _mark_and_move_broken(file_path, file, image_repos, bucket, prefix="Битый_ren_")
            continue

        try:
            with Image.open(file_path) as img:
                img = img.convert('RGB')
                raw_text = pytesseract.image_to_string(img, lang="rus+eng")
            texts[file] = LEGITIMAZE(raw_text)
        except pytesseract.TesseractError:
            _mark_and_move_broken(file_path, file, image_repos, bucket, prefix="OCRFail_ren_")
        except Exception:
            _mark_and_move_broken(file_path, file, image_repos, bucket, prefix="Битый_ren_")
    return texts

# ================== ПРИМЕР ЗАПУСКА ==================
if __name__ == "__main__":
    # Пример: собираем файлы из каталога репозитория изображений
    repo = os.path.abspath("./img_repo")
    os.makedirs(repo, exist_ok=True)
    all_files = [f for f in os.listdir(repo) if os.path.isfile(os.path.join(repo, f))]
    result = IMAGE_TEXT_EXTRACTOR(all_files, repo)
    print(f"OK: {len(result)} файлов с текстом")
