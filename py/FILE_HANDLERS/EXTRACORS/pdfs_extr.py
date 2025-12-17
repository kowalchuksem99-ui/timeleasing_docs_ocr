#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF extractors with Excel-like broken-file handling:
- PDF_TEXT_EXTRACTOR_FITZ  — быстрый текст из PDF (если текст встроен)
- PDF_TEXT_EXTRACTOR       — OCR через pytesseract (рендер страниц → OCR)
При ошибке: файл переименовывается (Битый_ren_*/OCRFail_ren_*) и переносится в Z:\<bucket>\Готовые.
"""

from __future__ import annotations
import io
import os
import re
import shutil
import time
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
import pytesseract
from PIL import Image as PILImage, ImageOps, Image as _PILBase

# ============ КОНФИГ ============
DEFAULT_PATH = r"Z:\\"
_PILBase.MAX_IMAGE_PIXELS = 178956970  # защита от слишком больших изображений

# Windows: укажи путь к tesseract, если он не в PATH
if os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = os.environ.get(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

# Ваш лемматизатор
from py.TEXT_HANDLERS.lemma import LEGITIMAZE


# ============ ХЕЛПЕРЫ (общие с Excel/IMG-логикой) ============

def extract_bucket(file_name: str) -> str:
    """
    Возвращает фамилию/номер папки по имени файла, игнорируя префиксы 'Битый[_ren]_'/ 'OCRFail_ren_'.
    Примеры: '(Иванов)_doc.pdf' -> 'Иванов', 'Петров_акт_1.pdf' -> 'Петров'
    """
    base = os.path.basename(file_name)
    stem = os.path.splitext(base)[0]
    stem = re.sub(r'^(?:Битый(?:_ren)?_|OCRFail_ren_)', '', stem, flags=re.IGNORECASE)

    if stem.startswith('(') and ')' in stem:
        return stem[1:stem.index(')')].strip()

    bucket = stem.split('_')[0].strip('() ')
    return bucket or "_"


def _unique_path(path: str) -> str:
    """Возвращает уникальный путь (добавляет счётчик, если занято)."""
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


def move_to_ready(file_path: str, file_name: str, bucket: str | None = None) -> None:
    """Перемещает файл в Z:\<bucket>\Готовые с уникальным именем."""
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


def _mark_and_move_broken(file_path: str, file_name: str, repos_dir: str, prefix: str = "Битый_ren_") -> None:
    """
    Переименовать файл в <prefix><name> внутри репозитория (с уникальностью)
    и затем переместить в Z:\<bucket>\Готовые.
    """
    bucket = extract_bucket(file_name)
    broken_name = f"{prefix}{file_name}"
    broken_path = os.path.join(repos_dir, broken_name)

    i = 1
    while os.path.exists(broken_path):
        broken_name = f"{prefix}{i}_{file_name}"
        broken_path = os.path.join(repos_dir, broken_name)
        i += 1

    try:
        os.replace(file_path, broken_path)
    except Exception as e:
        print(f"[RENAME:ERROR] {file_name}: {e}")
        broken_name = file_name
        broken_path = file_path

    move_to_ready(broken_path, broken_name, bucket)


# ============ ЭКСТРАКТОРЫ PDF ============

def PDF_TEXT_EXTRACTOR_FITZ(
    file_names: List[str],
    pdf_repos: str,
    store_timings: bool = False,
):
    """
    Извлекает встроенный текст из PDF средствами PyMuPDF.
    Возвращает texts или (texts, timings) при store_timings=True.
    texts:   {'file.pdf': 'лемматизированный текст', ...}
    timings: {'file.pdf': {'extract_secs': float}}
    """
    texts: Dict[str, str] = {}
    timings: Dict[str, Dict[str, float]] = {}

    for file in file_names:
        if "_ren_" in file:
            continue

        file_path = os.path.join(pdf_repos, file)
        print(f"\n⏳ Обрабатываю (fitz): {file}")

        doc = None
        try:
            doc = fitz.open(file_path)
            extract_time = 0.0
            chunks: List[str] = []

            for page in doc:
                p0 = time.perf_counter()
                page_text = page.get_text("text", sort=True)
                extract_time += time.perf_counter() - p0
                if page_text:
                    chunks.append(page_text)

            full_text = "\n".join(chunks)
            texts[file] = LEGITIMAZE(full_text)

            if store_timings:
                timings[file] = {"extract_secs": extract_time}
            print(f"  ▸ Извлечение текста: {extract_time:.2f} с")

        except Exception as exc:
            print(f"  ⚠ Ошибка: {exc}")
            _mark_and_move_broken(file_path, file, pdf_repos, prefix="Битый_ren_")
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    return (texts, timings) if store_timings else texts


def PDF_TEXT_EXTRACTOR(
    file_names: List[str],
    pdf_repos: str,
    *,
    dpi: int = 400,
    store_timings: bool = False,
):
    """
    OCR PDF при помощи PyMuPDF + Tesseract.
    Возвращает texts или (texts, timings) при store_timings=True.
    texts:   {'file.pdf': 'лемматизированный текст', ...}
    timings: {'file.pdf': {'render_secs': float, 'ocr_secs': float}}
    """
    texts: Dict[str, str] = {}
    timings: Dict[str, Dict[str, float]] = {}

    for file in file_names:
        if "_ren_" in file:
            continue

        file_path = os.path.join(pdf_repos, file)
        print(f"\n⏳ Обрабатываю (OCR): {file}")

        doc = None
        try:
            doc = fitz.open(file_path)
            render_time = 0.0
            ocr_time = 0.0
            chunks: List[str] = []

            for page in doc:
                p0 = time.perf_counter()
                pix = page.get_pixmap(dpi=dpi)     # рендер страницы
                render_time += time.perf_counter() - p0

                p1 = time.perf_counter()
                img_bytes = pix.tobytes("png")
                pil_img = PILImage.open(io.BytesIO(img_bytes))
                pil_img = ImageOps.autocontrast(ImageOps.grayscale(pil_img))

                ocr_text = pytesseract.image_to_string(
                    pil_img,
                    lang="rus",
                    config="--oem 3 --psm 6"
                )
                if ocr_text:
                    chunks.append(ocr_text)
                ocr_time += time.perf_counter() - p1

            full_text = "\n".join(chunks)
            texts[file] = LEGITIMAZE(full_text)

            if store_timings:
                timings[file] = {"render_secs": render_time, "ocr_secs": ocr_time}
            print(f"  ▸ Рендер: {render_time:.2f} с  |  OCR: {ocr_time:.2f} с")

        except pytesseract.TesseractError as exc:
            print(f"  ⚠ OCR ошибка: {exc}")
            _mark_and_move_broken(file_path, file, pdf_repos, prefix="OCRFail_ren_")
        except Exception as exc:
            print(f"  ⚠ Ошибка: {exc}")
            _mark_and_move_broken(file_path, file, pdf_repos, prefix="Битый_ren_")
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    return (texts, timings) if store_timings else texts


# ============ ПРИМЕР ЗАПУСКА ============

if __name__ == "__main__":
    repo = os.path.abspath("./pdf_repo")
    os.makedirs(repo, exist_ok=True)
    files = [f for f in os.listdir(repo) if f.lower().endswith(".pdf")]

    # 1) Встроенный текст
    texts1, t1 = PDF_TEXT_EXTRACTOR_FITZ(files, repo, store_timings=True)
    print(f"\n[fitz] ok: {len(texts1)} файлов")

    # 2) OCR
    texts2, t2 = PDF_TEXT_EXTRACTOR(files, repo, dpi=400, store_timings=True)
    print(f"[ocr ] ok: {len(texts2)} файлов")
