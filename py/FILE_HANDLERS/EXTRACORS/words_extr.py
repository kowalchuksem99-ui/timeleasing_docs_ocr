#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WORD_TEXT_EXTRACTOR: извлечение текста из Word с обработкой "битых" как в Excel/PDF/IMG.
Поддержка:
  - .docx — stdlib (zipfile + xml.etree)
  - .rtf  — наивный парсер (достаточно для служебных RTF)
  - .doc  — Unsupported (по умолчанию); опционально COM (pywin32) при USE_COM_FOR_DOC=1

При ошибке: файл переименуется (Битый_ren_* / Unsupported_ren_* / OCRFail_ren_* — не используется здесь)
и переместится в Z:\<bucket>\Готовые.
"""

from __future__ import annotations
import os
import re
import shutil
import zipfile
from typing import Dict, List

from xml.etree import ElementTree as ET

# ===== Конфиг (как в других модулях) =====
DEFAULT_PATH = r"Z:\\"

# Ваш лемматизатор
from py.TEXT_HANDLERS.lemma import LEGITIMAZE


# ===== Общие хелперы (совместимы с Excel/PDF/IMG) =====
def extract_bucket(file_name: str) -> str:
    """
    Возвращает фамилию/папку по имени, игнорируя префиксы 'Битый[_ren]_' / 'Unsupported_ren_'.
    Примеры: '(Иванов)_doc.docx' -> 'Иванов', 'Петров_акт_1.rtf' -> 'Петров'
    """
    base = os.path.basename(file_name)
    stem = os.path.splitext(base)[0]
    stem = re.sub(r'^(?:Битый(?:_ren)?_|Unsupported_ren_)', '', stem, flags=re.IGNORECASE)
    if stem.startswith('(') and ')' in stem:
        return stem[1:stem.index(')')].strip()
    bucket = stem.split('_')[0].strip('() ')
    return bucket or "_"

def _unique_path(path: str) -> str:
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

def _mark_and_move(file_path: str, file_name: str, repos_dir: str, prefix: str) -> None:
    """
    Переименовать в <prefix><file_name> (с уникальностью) внутри репозитория и
    переместить в Z:\<bucket>\Готовые.
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


# ===== Ридеры =====
def read_docx_text(path: str) -> str:
    """
    Извлекает текст из .docx без сторонних библиотек.
    Алгоритм: открыть ZIP, прочитать word/document.xml, собрать все w:t.
    """
    with zipfile.ZipFile(path) as zf:
        try:
            xml = zf.read("word/document.xml")
        except KeyError as e:
            raise ValueError("Файл не содержит word/document.xml (битый .docx)") from e
    # w: namespace для WordprocessingML
    NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ET.fromstring(xml)
    texts = []
    for t in root.findall(".//w:t", NS):
        if t.text:
            texts.append(t.text)
    # Доп. переносы по параграфам (w:p)
    # Если нужно жёстче разделять абзацы — можно вставлять '\n' по w:p.
    return " ".join(texts)

def read_rtf_text(path: str) -> str:
    """
    Наивная конвертация RTF->текст:
      - \par -> \n
      - \'hh -> байт в cp1251 (частый случай для русских RTF)
      - \\uN -> символ Юникод (грубо), игнор бэкапа
      - удаление управляющих слов/групп, { }
    Этого обычно достаточно для служебных актов/шаблонов.
    """
    raw = open(path, "rb").read()
    s = raw.decode("latin-1", errors="ignore")  # 1:1 байты->символы

    # \uN (16-bit signed) -> символ
    def _u2char(m):
        n = int(m.group(1))
        if n < 0:
            n += 65536
        return chr(n)
    s = re.sub(r"\\u(-?\d+)\??", _u2char, s)

    # \'hh -> байт -> cp1251
    def _hex2cp1251(m):
        b = bytes([int(m.group(1), 16)])
        return b.decode("cp1251", errors="replace")
    s = re.sub(r"\\'([0-9a-fA-F]{2})", _hex2cp1251, s)

    # \par -> newline
    s = s.replace(r"\par", "\n")

    # убрать прочие управляющие слова \word123?
    s = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", s)

    # убрать группы/braces и лишние слэши
    s = s.replace("{", "").replace("}", "").replace("\\", "")

    # финальная зачистка пробелов
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def read_doc_via_com(path: str) -> str:
    """
    Опциональный ридер .doc через COM-автоматизацию Word (Windows + pywin32).
    Включается, если переменная окружения USE_COM_FOR_DOC = "1".
    """
    if os.name != "nt" or os.environ.get("USE_COM_FOR_DOC") != "1":
        raise RuntimeError("COM для .doc отключен (USE_COM_FOR_DOC!=1)")

    try:
        import tempfile
        import win32com.client  # type: ignore
    except Exception as e:
        raise RuntimeError("pywin32 не установлен или недоступен") from e

    wdFormatText = 2  # сохранение в .txt
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    tmp_txt = None
    try:
        doc = word.Documents.Open(path, ReadOnly=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp_txt = tmp.name
        doc.SaveAs(tmp_txt, FileFormat=wdFormatText)
        doc.Close(False)
        with open(tmp_txt, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    finally:
        try:
            word.Quit()
        except Exception:
            pass
        if tmp_txt and os.path.exists(tmp_txt):
            try:
                os.remove(tmp_txt)
            except Exception:
                pass


# ===== Основная функция =====
def WORD_TEXT_EXTRACTOR(file_names: List[str], word_repos: str) -> Dict[str, List[str]]:
    """
    Извлекает текст из .docx/.rtf/.doc и возвращает:
      {'имя_файла': [леммы...], ...}
    Ошибки/неподдерживаемые — переименование (префикс) + перенос в Z:\<bucket>\Готовые.
    """
    texts: Dict[str, List[str]] = {}

    for file in file_names:
        if "_ren_" in file:
            continue  # уже помеченные пропускаем

        file_path = os.path.join(word_repos, file)
        ext = os.path.splitext(file)[1].lower()
        print(f"\n⏳ Обрабатываю (WORD): {file}")

        try:
            if ext in (".docx",):
                raw_text = read_docx_text(file_path)
            elif ext in (".rtf",):
                raw_text = read_rtf_text(file_path)
            elif ext in (".doc",):
                try:
                    raw_text = read_doc_via_com(file_path)  # может бросить RuntimeError
                except Exception as e:
                    # .doc без COM считаем неподдерживаемым
                    raise RuntimeError(f".doc не поддержан: {e}") from e
            else:
                raise ValueError(f"Неподдерживаемое расширение: {ext}")

            lemmas = [w for w in LEGITIMAZE(raw_text) if w != "nan"]
            texts[file] = lemmas

        except ValueError as e:
            print(f"  ⚠ Ошибка: {e}")
            _mark_and_move(file_path, file, word_repos, prefix="Битый_ren_")
        except RuntimeError as e:
            print(f"  ⚠ Unsupported: {e}")
            _mark_and_move(file_path, file, word_repos, prefix="Unsupported_ren_")
        except Exception as e:
            print(f"  ⚠ Неизвестная ошибка: {e}")
            _mark_and_move(file_path, file, word_repos, prefix="Битый_ren_")

    return texts


# ===== Пример запуска =====
if __name__ == "__main__":
    repo = os.path.abspath("./word_repo")
    os.makedirs(repo, exist_ok=True)
    files = [f for f in os.listdir(repo) if os.path.isfile(os.path.join(repo, f))]
    res = WORD_TEXT_EXTRACTOR(files, repo)
    print(f"\nOK: {len(res)} файлов обработано")
