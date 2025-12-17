import os
import re
import calendar
from typing import Iterable, Tuple
from py.FILE_HANDLERS.EXTRACORS.pdfs_extr import PDF_TEXT_EXTRACTOR_FITZ
from pathlib import Path
from datetime import datetime, date, timedelta



MONTHS = {
    "января": "01", "январь": "01", "февраля": "02", "февраль": "02",
    "марта": "03", "март": "03", "апреля": "04", "апрель": "04",
    "мая": "05", "май": "05", "июня": "06", "июнь": "06",
    "июля": "07", "июль": "07", "августа": "08", "август": "08",
    "сентября": "09", "сентябрь": "09", "октября": "10", "октябрь": "10",
    "ноября": "11", "ноябрь": "11", "декабря": "12", "декабрь": "12"
}

# Якорь заголовка ОСВ (ловит и "Оборотно-сальдовая", и "Оборотно – сальдовая")
OSV_HEADER = re.compile(
    r"оборотно\s*[-–—]?\s*сальдов[а-я]+\s+ведомост[ьи][^\n]{0,300}",
    re.I
)

def _osv_focus_window(text: str, pre: int = 200, post: int = 2500) -> str | None:
    """
    Возвращает компактное окно вокруг заголовка ОСВ.
    pre/post подбираются эмпирически: дату почти всегда пишут
    в пределах пары тысяч символов после заголовка.
    """
    m = OSV_HEADER.search(text)
    if not m:
        return None
    start = max(0, m.start() - pre)
    end = min(len(text), m.end() + post)
    return text[start:end]


def _month_to_num(month_txt: str) -> str | None:
    """По префиксу рус. названия месяца → '01'..'12'. Возвращает None, если не распознано."""
    month_txt = month_txt.lower()
    mapping = {
        "январ": "01", "феврал": "02", "март": "03", "апрел": "04",
        "май": "05", "мая": "05", "июн": "06", "июл": "07", "август": "08",
        "сентябр": "09", "октябр": "10", "ноябр": "11", "декабр": "12"
    }
    for k, v in mapping.items():
        if month_txt.startswith(k):
            return v
    return None

def _eom(yyyy: int, mm: int) -> int:
    """Последний день месяца."""
    return calendar.monthrange(yyyy, mm)[1]

def _eom_str(yyyy: int, mm: int) -> str:
    return f"{_eom(yyyy, mm):02}.{mm:02}.{yyyy}"

def _prev_month_eom(yyyy: int, mm: int) -> str:
    """Последний день предыдущего месяца от (yyyy, mm, 1)."""
    first = date(yyyy, mm, 1)
    prev_last = first - timedelta(days=1)
    return prev_last.strftime("%d.%m.%Y")

def _parse_ddmmyyyy(s: str) -> tuple[int, int, int]:
    dd, mm, yyyy = map(int, re.split(r"[./-]", s))
    return dd, mm, yyyy


def strip_account(text: str) -> str:
    """Удаляет 'счёт 01', 'счет №58', 'счёт  60' и т.п. (регистр не важен)."""
    return re.compile(r'сч[её]т\s+№?\s*\d+\s*', re.I).sub('', text)


def normalize_kart51_date(raw_date: str) -> str:
    t = raw_date.strip().lower()

    # 1) диапазон DD.MM.YYYY – DD.MM.YYYY
    m = re.search(r"(\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2})\s*[-–—]\s*(\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2})", t)
    if m:
        end_dd, end_mm, end_yyyy = _parse_ddmmyyyy(m.group(2))
        # если конец не последний день месяца → берем конец ПРЕДЫДУЩЕГО месяца
        if end_dd != _eom(end_yyyy, end_mm):
            return _prev_month_eom(end_yyyy, end_mm)
        return f"{end_dd:02}.{end_mm:02}.{end_yyyy}"

    # 2) '1 квартал 2024' → конец квартала
    m = re.search(r"(\d)\s*квартал\s+(\d{4})", t)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return _eom_str(y, q * 3)

    # 3) 'Август 2024 – Сентябрь 2024' → последний день второго месяца
    month_pairs = re.findall(rf"({NOISY_MONTH})\s+(\d{{4}})", t, re.I)
    if len(month_pairs) >= 2:
        last_mon_txt, last_y = month_pairs[-1]
        mm = _month_to_num(last_mon_txt)
        if mm:
            return _eom_str(int(last_y), int(mm))

    # 4) одиночный 'Февраль 2025' → последний день месяца
    m = re.search(rf"({NOISY_MONTH})\s+(\d{{4}})", t, re.I)
    if m:
        mm = _month_to_num(m.group(1))
        yy = int(m.group(2))
        if mm:
            return _eom_str(yy, int(mm))

    return "no-date"


def parse_declaration_date(text: str, *, allow_fallback: bool = True) -> str:
    """
    'код 3 3 ... год 2 0 2 4' -> дата конца квартала.
    Если allow_fallback=True и код не найден, пробуем квартал или просто год.
    """
    pat = re.compile(r"код\s*(2\s*1|3\s*1|3\s*3|3\s*4).*?год\s*(2\s*\d\s*\d\s*\d)", re.I | re.S)
    m = pat.search(text)
    if m:
        code = re.sub(r"\s+", "", m.group(1))
        year = re.sub(r"\s+", "", m.group(2))
        return {"21": f"31.03.{year}", "31": f"30.06.{year}", "33": f"30.09.{year}", "34": f"31.12.{year}"}.get(code, "no-date")

    if not allow_fallback:
        return "no-date"

    # 1) '1 квартал 2024'
    m = re.search(r"(\d)\s*квартал\s+(\d{4})", text, re.I)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return _eom_str(y, q * 3)

    # 2) 'за 2023 г.' → 31.12.2023
    m = re.search(r"(?:за\s+)?(19|20)\d{2}\s*г\.?", text, re.I)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        return f"31.12.{y}"

    return "no-date"



def normalize_osv_date(raw_date: str) -> str:
    t = raw_date.strip().lower()

    # A) Диапазон DD.MM.YYYY – DD.MM.YYYY
    m = re.search(r"(\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2})\s*[-–—]\s*(\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2})", t)
    if m:
        end_dd, end_mm, end_yyyy = _parse_ddmmyyyy(m.group(2))
        if end_dd != _eom(end_yyyy, end_mm):
            return _prev_month_eom(end_yyyy, end_mm)
        return f"{end_dd:02}.{end_mm:02}.{end_yyyy}"

    # B) Диапазон 'Месяц ГГГГ – Месяц ГГГГ'
    month_pairs = re.findall(rf"({NOISY_MONTH})\s+(\d{{4}})", t, re.I)
    if len(month_pairs) >= 2:
        last_mon_txt, last_y = month_pairs[-1]
        mm = _month_to_num(last_mon_txt)
        if mm:
            return _eom_str(int(last_y), int(mm))

    # C) Квартал
    m = re.search(r"(?:№\s*)?(\d)\s*квартал\s+(\d{4})", t)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return _eom_str(y, q * 3)

    # C.4) "за N месяц(ев) YYYY" → конец месяца N (год-to-date)
    m = re.search(r"(?:за\s*)?(\d{1,2})\s*(?:месяц(?:ев)?|мес\.?)\s+(\d{4})", t, re.I)
    if m:
        n, y = int(m.group(1)), int(m.group(2))
        if 1 <= n <= 12:
            return _eom_str(y, n)

    # C.5) Полугодие — ДОЛЖНО быть раньше «просто год»
    m = re.search(r"(?:за\s*)?(\d)\s*полугодие\s+(\d{4})", t, re.I)
    if m:
        half, y = int(m.group(1)), int(m.group(2))
        return _eom_str(y, 6 * half)  # 1 → 30.06.YYYY, 2 → 31.12.YYYY

    # D) Конкретная дата 'на 24 февраля 2025'
    m = re.search(rf"(?:на\s+)?(\d{{1,2}})\s+({NOISY_MONTH})\s+(\d{{4}})", t, re.I)
    if m:
        dd = int(m.group(1)); mm = _month_to_num(m.group(2)); yy = int(m.group(3))
        if mm:
            return f"{dd:02}.{int(mm):02}.{yy}"

    # E) Одиночный 'месяц-год'
    m = re.search(rf"({NOISY_MONTH})\s+(\d{{4}})", t, re.I)
    if m:
        mm = _month_to_num(m.group(1)); yy = int(m.group(2))
        if mm:
            return _eom_str(yy, int(mm))

    # F) «За 2024 г.» — общий фолбэк (ставим ПОСЛЕ «полугодия»!)
    m = re.search(r"\b(19|20)\d{2}\s*г\.?", t)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        return f"31.12.{y}"

    return "no-date"


def normalize_f1_date(raw_date: str) -> str:
    """
    '… баланс 30 Июня 2024 г.' → '30.06.2024'
    Работает и c '… баланс на 30 июня 2024 г.'
    """
    print("Текст Ф1: ", raw_date)
    m = re.search(
        r"(?:на\s+)?(\d{1,2})\s+"  # ❰день❱  с optional «на»
        r"(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|"
        r"июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|"
        r"ноябр[ья]|декабр[ья])\s+(\d{4})",
        raw_date, re.I,
    )
    print("Совпадение даты в Ф1: ", m)
    if not m:
        return "no-date"

    day, month_txt, year = int(m.group(1)), m.group(2), m.group(3)
    month = _month_to_num(month_txt)
    return f"{day:02}.{month}.{year}" if month else "no-date"

# --- настройки «головы» документа ---
HEAD_PCT = 40           # первые N% текста
HEAD_MAXCHARS = 8000    # и не больше N символов

def _head(text: str, pct: int = HEAD_PCT, max_chars: int = HEAD_MAXCHARS) -> str:
    end = min(len(text), max_chars, int(len(text) * pct / 100))
    return text[:end]

_SIG_TAIL = re.compile(
    r"(?:подпис\w*|расшифровк\w*|руководител\w*|главн\w*\s+бухгалтер\w*|м\.п\.|печать)[\s\S]{0,2000}$",
    re.I
)

def _strip_signature_tails(text: str) -> str:
    m = _SIG_TAIL.search(text)
    return text[:m.start()] if m else text

def _infer_period_end_generic(text: str) -> str:
    # квартал
    m = re.search(r"(\d)\s*квартал\s+(\d{4})", text, re.I)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return _eom_str(y, q * 3)

    # месяц–месяц–год
    m = re.search(rf"({NOISY_MONTH})\s*[-–—]\s*({NOISY_MONTH})\s+(\d{{4}})", text, re.I)
    if m:
        mm2 = _month_to_num(m.group(2))
        if mm2:
            return _eom_str(int(m.group(3)), int(mm2))

    # просто год
    m = re.search(r"(19|20)\d{2}\s*г\.?", text, re.I)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        return f"31.12.{y}"

    return "no-date"

FLEX_SEP = r"(?:[\s.,;:()\\[\\]«»\"'|/\\\\]+|[-–—])"  # любые пробелы/знаки/тире

def _fallback_month_year_sweep(text: str) -> str:
    t = text.lower()

    # прибьём коды формы, чтобы 0710 и т.п. не мешали
    t = re.sub(r"форма\s*\d{4,7}", " ", t)
    t = re.sub(r"\b0\d{3}\b", " ", t)

    # 1) месяц–месяц … год (до ~200 любых символов между токенами)
    mm_range = re.findall(
        rf"({NOISY_MONTH}).{{0,80}}?({NOISY_MONTH}).{{0,200}}?((?:19|20)\d{{2}})",
        t, flags=re.I | re.S
    )
    if mm_range:
        mon2, y = mm_range[-1][1], int(mm_range[-1][2])  # берём последний диапазон
        mm2 = _month_to_num(mon2)
        if mm2:
            return _eom_str(y, int(mm2))

    # 2) самая поздняя пара «месяц … год» (разрешаем небольшой шум между)
    pairs = []
    for mon, y in re.findall(
        rf"({NOISY_MONTH}).{{0,40}}?((?:19|20)\d{{2}})", t, flags=re.I | re.S
    ):
        mm = _month_to_num(mon)
        if mm:
            pairs.append((int(y), int(mm)))
    if pairs:
        y, m = max(pairs)
        return _eom_str(y, m)

    # 3) просто год
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", t)]
    if years:
        return f"31.12.{max(years)}"

    return "no-date"


def normalize_f2_date(raw_date: str) -> str:
    t = raw_date.lower().strip()

    # 1) 'за Январь – Июнь 2023'
    m = re.search(rf"(?:за\s+)?({NOISY_MONTH})\s*[-–—]\s*({NOISY_MONTH})\s+(\d{{4}})\s*г?\.?", t, re.I)
    if m:
        mon2, y = m.group(2), int(m.group(3))
        mm2 = _month_to_num(mon2)
        if mm2:
            return _eom_str(y, int(mm2))

    # 1.1) 'на февраль 2022 г.' / 'за февраль 2022 г.' / 'по состоянию на февраль 2022'
    m = re.search(rf"(?:на\s+|за\s+|по\s+состоянию\s+на\s+)?({NOISY_MONTH})\s+(\d{{4}})\s*г?\.?", t, re.I)
    if m:
        mm = _month_to_num(m.group(1))
        y = int(m.group(2))
        if mm:
            return _eom_str(y, int(mm))

    # 2) 'за 2023 г.' → 31.12.2023
    m = re.search(r"(?:за\s+)?(19|20)\d{2}\s*г\.?", t)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        return f"31.12.{y}"

    # 3) 'на 15 февраля 2022 г.' → 15.02.2022
    m = re.search(rf"(?:на\s+|по\s+состоянию\s+на\s+)?(\d{{1,2}})\s+({NOISY_MONTH})\s+(\d{{4}})\s*г?\.?", t, re.I)
    if m:
        dd = int(m.group(1)); mm = _month_to_num(m.group(2)); yy = int(m.group(3))
        if mm:
            return f"{dd:02}.{int(mm):02}.{yy}"

    return "no-date"

def normalize_kp_date(raw: str) -> str:
    """
    Нормализует дату из шаблонов для КП, включая диапазоны:
    - 05.07.2024
    - 2024-07-05
    - Контрагенты за 01.01.2024 - 31.03.2024
    """
    raw = raw.lower()

    # 1. Диапазон ДД.ММ.ГГГГ – ДД.ММ.ГГГГ
    m = re.search(r"\b(\d{1,2})[.\-‑–—](\d{1,2})[.\-‑–—](\d{4})\s*[-‑–—]\s*(\d{1,2})[.\-‑–—](\d{1,2})[.\-‑–—](\d{4})", raw)
    if m:
        dd2, mm2, yyyy2 = m.group(4), m.group(5), m.group(6)
        return f"{int(dd2):02}.{int(mm2):02}.{yyyy2}"

    # 2. Диапазон ГГГГ.ММ.ДД – ГГГГ.ММ.ДД
    m = re.search(r"\b(\d{4})[.\-‑–—](\d{1,2})[.\-‑–—](\d{1,2})\s*[-‑–—]\s*(\d{4})[.\-‑–—](\d{1,2})[.\-‑–—](\d{1,2})", raw)
    if m:
        yyyy2, mm2, dd2 = m.group(4), m.group(5), m.group(6)
        return f"{int(dd2):02}.{int(mm2):02}.{yyyy2}"

    # 3. Одиночная дата ДД.ММ.ГГГГ
    m = re.search(r"\b(\d{1,2})[.\-‑–—](\d{1,2})[.\-‑–—](\d{4})", raw)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{int(dd):02}.{int(mm):02}.{yyyy}"

    # 4. ГГГГ.ММ.ДД
    m = re.search(r"\b(\d{4})[.\-‑–—](\d{1,2})[.\-‑–—](\d{1,2})", raw)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{int(dd):02}.{int(mm):02}.{yyyy}"

    # 5. "ДД" месяц ГГГГ
    m = re.search(r'"?(\d{1,2})"?\s*(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|'
                  r'июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|'
                  r'ноябр[ья]|декабр[ья])\s+(\d{4})', raw)
    if m:
        dd, month_txt, yyyy = m.groups()
        month = _month_to_num(month_txt)
        return f"{int(dd):02}.{month}.{yyyy}"

    # 6. Только месяц и год
    m = re.search(r"(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|"
                  r"июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|"
                  r"ноябр[ья]|декабр[ья])\s+(\d{4})", raw)
    if m:
        month_txt, yyyy = m.groups()
        month = _month_to_num(month_txt)
        return f"01.{month}.{yyyy}"

    return "no-date"


def normalize_lp_date(raw: str) -> str:
    """
    Нормализует дату для «ЛП» (лизинговый портфель).
    Поддерживает:
      • «Контрагенты за 15 июня 2024»
      • «дата 05.07.2024»
      • «… на 2024-07-05»
      • диапазоны «05.07.2024 – 31.12.2024» и «2024.07.05 – 2024.12.31»
      • «июнь 2024» и т.п.
    Возвращает последнюю дату диапазона либо одиночную дату
    в формате DD.MM.YYYY, иначе "no-date".
    """
    import re

    # Убираем служебные фразы
    txt = re.sub(
        r"(контрагенты\s+за|дата\s+|лизинговый\s+портфель\s+на|"
        r"расшифровка\s+текущи[йх]\s+обязательств(?:о|а)?(?:\s+по\s+договора?м?\s+лизинг(?:а|у|ом)?)?\s+на|"
        r"дата\s+состав\w+\s+|кредитно-лизинговый\s+портфель\s+на|"
        r"резерв\s+на|остаток\s+на|остаток\s+задолженност[ьи]?\s+на)",
        "", raw, flags=re.I
    ).lower()

    # Убираем «г.» / «г»
    txt = re.sub(r"\s+г\.?\b", "", txt)

    # Расширение двухзначных годов
    def _expand_yy(m: re.Match) -> str:
        dd, mm, yy = m.groups()
        yyyy = f"20{yy}" if int(yy) < 50 else f"19{yy}"
        return f"{int(dd):02}.{int(mm):02}.{yyyy}"

    txt = re.sub(
        r"\b(\d{1,2})[.\-–—](\d{1,2})[.\-–—](\d{2})\b",
        _expand_yy,
        txt,
    )

    return normalize_kp_date(txt)


NOISY_MONTH = r"(?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])"

def _collect_all_dates_ru(text: str) -> list[str]:
    """
    Собирает все даты вида 'DD.MM.YYYY' и 'DD месяц YYYY' → нормализует в 'DD.MM.YYYY'.
    """
    out: list[str] = []

    # 1) DD.MM.YYYY
    for m in re.finditer(r"\b(\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2})\b", text):
        dd, mm, yyyy = _parse_ddmmyyyy(m.group(1))
        out.append(f"{dd:02}.{mm:02}.{yyyy}")

    # 2) DD <месяц> YYYY
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({NOISY_MONTH})\s+((?:19|20)\d{{2}})\b", text, re.I):
        dd = int(m.group(1))
        mm = _month_to_num(m.group(2))
        yyyy = int(m.group(3))
        if mm:
            out.append(f"{dd:02}.{int(mm):02}.{yyyy}")

    return out

def normalize_anketa_date(full_text: str) -> str:
    """
    Для «Анкета» выбираем последнюю (максимальную) дату из всех найденных.
    Это позволит отсечь случайные старые даты (напр., 27.07.2006).
    """
    dates = _collect_all_dates_ru(full_text)
    # разумный коридор
    filtered = []
    for d in dates:
        dd, mm, yyyy = map(int, d.split("."))
        if 2000 <= yyyy <= 2100:
            filtered.append((yyyy, mm, dd, d))
    if not filtered:
        return "no-date"
    filtered.sort()
    return filtered[-1][-1]  # строка 'DD.MM.YYYY'


def normalize_kpi_lp_date(raw: str) -> str:
    """
    Специальный нормализатор для класса «КПиЛП».

    • «На текущую дату»      → сегодняшняя дата
    • «… на март 2024 г.»    → 01.03.2024
    • «… на 15.04.2025 г.»   → 15.04.2025
    • остальные диапазоны / одиночные даты → через normalize_lp_date / normalize_kp_date
    """
    txt = raw.lower().strip()

    # --- 1. «На текущую дату»
    if re.search(r"на\s+текущий\w*\s+дат[уыа]", txt):
        return datetime.today().strftime("%d.%m.%Y")

    # --- 2. срезаем служебные фразы перед датой
    txt = re.sub(
        r"(лизинговый\s+портфель\s+на|"
        r"краткосрочные\s+и\s+долгосрочные\s+кредиты\s+и\s+займы\s+на)",
        "",
        txt,
        flags=re.I,
    ).strip()

    # --- 3. дальше работают уже написанные нормализаторы
    res = normalize_lp_date(txt)
    if res == "no-date":
        res = normalize_kp_date(txt)
    return res

CLASS_PRESETS = {
    "Анкета": {
        "regex": re.compile(r"""\b((?:["«„“])?\d{1,2}(?:["»“”])?\s*(?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\s+\d{4}\s*год|
                   \d{2}\.\d{2}\.\d{4})\b""", re.IGNORECASE | re.VERBOSE),
        "slice": (90, 100),
        "regex_date": lambda a: re.sub(r"[гГ]од[а-я]*\.?|[,\s]+|[«»“”\"]", " ", a).strip().lower()
    },
    "Декларация": {
        "regex": re.compile(r"""
                     налоговый
                     \s*отч[её]тн[а-я]+
                     \s*период
                     \s*код
                     \s*(?:2\s*1|3\s*1|3\s*3|3\s*4)
                     \s*отч[её]тн[а-я]+
                     \s*год
                     \s*(?:2\s*\d\s*\d\s*\d)
                    """, re.IGNORECASE | re.VERBOSE),
        "slice": (0, 30),
        "regex_date": lambda s: parse_declaration_date(s, allow_fallback=True)
    },
    "Карточка51": {
        "regex": re.compile(r"""
        (
            (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
               июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
               ноябр[ья]|декабр[ья])
            \s+
            \d{4}
            (?:\s+г\.)?
        )
        (?:
            \s*[-–]\s*
            (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
               июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
               ноябр[ья]|декабр[ья])
            \s+
            \d{4}
            (?:\s+г\.)?
        )?
        |
        (
            \d{2}[./-]\d{2}[./-]\d{4}
            \s*[-–]\s*
            \d{2}[./-]\d{2}[./-]\d{4}
        )
        |
        (
            \d{1,2}\s+квартал\s+\d{4}\s+г\.)
        """, re.IGNORECASE | re.VERBOSE),
        "slice": (0, 10),
        "regex_date": lambda a: normalize_kart51_date(a)
    },
    "ОСВ": {
        "regex": re.compile(r"""
                (?:№\s*)?(\d{1,2})\s*квартал\s+(\d{4})\s*г\.?      # 1-й квартал
            |
                (?:за\s+)?                                         # месяц-год
                (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}\s*г?\.?
            |
                (?:за\s+)?                                         # месяц-месяц
                ((?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}\s*г?\.?)
                \s*[-–—-]\s*
                ((?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}\s*г?\.?)
            |
                (\d{2}[./-]\d{2}[./-]\d{4})\s*[-–-]\s*(\d{2}[./-]\d{2}[./-]\d{4})
            |
                За\s+(\d{4})\s*г\.?
            |
                За\s+\d+\s+месяц(?:ев)?\s+(\d{4})\s*г\.?
            |
                За\s+\d+\s+полугодие\s+(\d{4})\s*г\.?
            |
                (\d{1,2})\s*(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                    июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                    ноябр[ья]|декабр[ья])\s+(\d{4})
            |
                (\d{1,2})\s*(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                    июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                    ноябр[ья]|декабр[ья])\s+(\d{4})\s*[-–]\s*
                (\d{1,2})\s*(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                    июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                    ноябр[ья]|декабр[ья])\s+(\d{4})
            """, re.IGNORECASE | re.VERBOSE),
        "slice": (0, 100),
        "regex_date": lambda a: normalize_osv_date(a)
    },
    "Ф1": {
        "regex": re.compile(r"бухгалтерск[ийая]+\s+баланс\s+"  # Бухгалтерский баланс
                            r"(?:на\s+)?\s*"  # ▸ «на» может быть, а может и нет
                            r"\d{1,2}\s+"  # ▸ число
                            r"(?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|"
                            r"июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|"
                            r"ноябр[ья]|декабр[ья])\s+"  # ▸ месяц словом
                            r"\d{4}\s*г?\.?", re.IGNORECASE),
        "slice_first": (0, 15),
        "slice_sec": (85, 100),
        "regex_date": lambda a: normalize_f1_date(a)
    },
    "Ф2": {
        "regex": re.compile(
            rf"(?:на\s+|по\s+состоянию\s+на\s+)?\d{{1,2}}\s+{NOISY_MONTH}\s+\d{{4}}\s*г?\.?"   # день-месяц-год
            rf"|(?:на\s+|за\s+|по\s+состоянию\s+на\s+)?{NOISY_MONTH}\s+\d{{4}}\s*г?\.?"       # ← МЕСЯЦ-ГОД (новое)
            rf"|(?:за\s+)?{NOISY_MONTH}\s*[-–—]\s*{NOISY_MONTH}\s+\d{{4}}\s*г?\.?"           # месяц–месяц–год
            rf"|\b(?:за\s+)?(?:19|20)\d{{2}}\b\s*г?\.?",                                                 # год (фолбэк)
            re.IGNORECASE
        ),
        "slice_first": (0, 50),
        "slice_sec": (90, 100),
        "regex_date": lambda a: normalize_f2_date(a)
    },
    "КП": {
        "regex": re.compile(r"""
            (?:
                (?:
                    Дата\s+|   
                    \b(ОАО|ООО|ЗАО|ПАО|НАО|АО)\s+\S+\s+На\s+|                           
                    Контрагент(?:ы)?\s+за\s+|                
                    По\s+состояни[юе]\s+на\s+|               
                    Отч[её]тн[ыа][йя]\s+дата\s+|             
                    По\s+кредитам\s+и\s+займам\s+по\s+состоянию\s+на\s+
                )
                (?:
                    # Диапазон: дата - дата (любой формат)
                    (?P<range1>\d{1,2})[.\-‑–—](?P<range2>\d{1,2})[.\-‑–—](?P<range3>\d{4})
                    \s*[-‑–—]\s*
                    (?P<range4>\d{1,2})[.\-‑–—](?P<range5>\d{1,2})[.\-‑–—](?P<range6>\d{4})
                    |
                    (?P<range_y1>\d{4})[.\-‑–—](?P<range_m1>\d{1,2})[.\-‑–—](?P<range_d1>\d{1,2})
                    \s*[-‑–—]\s*
                    (?P<range_y2>\d{4})[.\-‑–—](?P<range_m2>\d{1,2})[.\-‑–—](?P<range_d2>\d{1,2})
                    |
                    (?P<dd>\d{1,2})[.\-‑–—](?P<mm>\d{1,2})[.\-‑–—](?P<yyyy>\d{4})
                    |
                    (?P<yyyy2>\d{4})[.\-‑–—](?P<dd2>\d{1,2})[.\-‑–—](?P<mm2>\d{1,2})
                    |
                    (?:"?(?P<qdd>\d{1,2})"?)?\s*
                    (?P<mon>январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|
                          сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\s+(?P<y4>\d{4})\s*г?\.?
                )
            )
        """, re.IGNORECASE | re.VERBOSE),
        "slice": (0, 100),
        "regex_date": lambda raw: normalize_kp_date(raw)
    },
    "ЛП": {
        "regex": re.compile(r"""
        (?:
            # ────────────────────────────────────────────────────────────────
            # 1.  Дата идёт СРАЗУ ПОСЛЕ длинной полосы из 5+ тире/минусов
            # ────────────────────────────────────────────────────────────────
            [-–—]{5,}      # ≥ 5 символов '-','–','—' подряд
            \s*            # пробелы/переносы строки
            (?:
                \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})      # dd.mm.yyyy | dd.mm.yy
              | \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}                # yyyy.mm.dd
              | \d{4}-\d{2}-\d{2}                                # yyyy-mm-dd
              | "?\d{1,2}"?\s*
                (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}                 # «15 июня 2024»
              | (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}                 # «июнь 2024»
            )
        )
        |
        (?:
            # ────────────────────────────────────────────────────────────────
            # 2.  Старая логика: ключевая фраза + дата/диапазон
            # ────────────────────────────────────────────────────────────────
            (?:Контрагенты\s+за|Дата\s+|Лизинговый\s+портфель\s+на|
               расшифровка\s+текущи[йх]\s+обязательств(?:о|а)?
                   (?:\s+по\s+договор\w*\s+лизинг(?:а|у|ом)?)?\s+на|
               дата\s+состав\w+\s+|Кредитно-лизинговый\s+портфель\s+на|
               Резерв\s+на|Остаток\s+на|Остаток\s+задолженност[ьи]?\s+на)
            \s*
            (?:
                \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})\s*[–—]\s*
                    \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})   # dd.mm.yyyy – dd.mm.yyyy
              | \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}\s*[–—]\s*
                    \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}             # yyyy.mm.dd – yyyy.mm.dd
              | \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})       # одиночная dd.mm.yyyy/yy
              | \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}                 # одиночная yyyy.mm.dd
              | \d{4}-\d{2}-\d{2}                                 # одиночная yyyy-mm-dd
              | "?\d{1,2}"?\s*
                (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}                 # «15 июня 2024»
              | (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}                 # «июнь 2024»
            )
        )
        """, re.I | re.VERBOSE),
        "slice": (0, 100),
        "regex_date": lambda a: normalize_lp_date(a)
    },
    "КПиЛП": {
        "regex": re.compile(r"""
        (?:
            # ════════════════════════════════════════════════════════
            # 1.   «На текущую дату»
            # ════════════════════════════════════════════════════════
            На\s+текущий\w*\s+дат[уыа]            # допускаем «текущую / текущей»
        )
        |
        (?:
            # ════════════════════════════════════════════════════════
            # 2.   «Лизинговый портфель на март 2024 г.»
            # ════════════════════════════════════════════════════════
            Лизинговый\s+портфель\s+на\s+
            (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
               июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
               ноябр[ья]|декабр[ья])
            \s+\d{4}\s*г?\.?
        )
        |
        (?:
            # ════════════════════════════════════════════════════════
            # 3.   «Краткосрочные и долгосрочные кредиты и займы на 15.04.2025 г.»
            # ════════════════════════════════════════════════════════
            Краткосрочные\s+и\s+долгосрочные\s+кредиты\s+и\s+займы\s+на\s+
            \d{1,2}[./-]\d{1,2}[./-]\d{4}\s*г?\.?
        )
        |
        (?:
            # ════════════════════════════════════════════════════════
            # 4.   ВСЯ ваша старая логика (диапазоны, одиночные даты, месяцы)
            # ════════════════════════════════════════════════════════
            (?:Контрагенты\s+за|Дата\s+|Лизинговый\s+портфель\s+на|
               расшифровка\s+текущи[йх]\s+обязательств(?:о|а)?
                   (?:\s+по\s+договор\w*\s+лизинг(?:а|у|ом)?)?\s+на|
               дата\s+состав\w+\s+|Кредитно-лизинговый\s+портфель\s+на|
               Резерв\s+на|Остаток\s+на|Остаток\s+задолженност[ьи]?\s+на)
            \s*
            (?:
                \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})\s*[–—]\s*
                    \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})        # диапазон dd.mm – dd.mm
              | \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}\s*[–—]\s*
                    \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}                  # диапазон yyyy.mm.dd – …
              | \d{1,2}[.\-–—]\d{1,2}[.\-–—](?:\d{4}|\d{2})            # одиночная dd.mm.yyyy
              | \d{4}[.\-–—]\d{1,2}[.\-–—]\d{1,2}                      # одиночная yyyy.mm.dd
              | \d{4}-\d{2}-\d{2}                                      # одиночная yyyy-mm-dd
              | "?\d{1,2}"?\s*
                (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}\s*г?\.?              # «15 июня 2024»
              | (?:январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|
                   июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|
                   ноябр[ья]|декабр[ья])\s+\d{4}\s*г?\.?              # «июнь 2024»
            )
        )
        """, re.I | re.VERBOSE),
        "slice": (0, 100),
        "regex_date": lambda a: normalize_kpi_lp_date(a)
    },
    "Ф1+Ф2": {
        "regex_f1": re.compile(r"бухгалтерск\w*\s+баланс", re.I),
        "regex_f2": re.compile(r"отч[её]т\s+финанс", re.I),
        "slice": (0, 100)
    },
}

folder_path: str = r"Z:\\"

def split_f1_f2(text: str) -> tuple[str | None, str | None]:
    low = text.lower()
    m1 = CLASS_PRESETS["Ф1+Ф2"]["regex_f1"].search(low)
    m2 = CLASS_PRESETS["Ф1+Ф2"]["regex_f2"].search(low)
    if not m1 or not m2 or m2.start() <= m1.start():
        return None, None
    return text[m1.start():m2.start()], text[m2.start():]

def date_change(date: str, cls: str) -> str:
    """
    Преобразует формат дат в документах в формат DD.MM.YYYY
    :param date:
    :param cls:
    :return:
    """
    match cls:
        case "Анкета":
            clean = CLASS_PRESETS["Анкета"]["regex_date"](date)
            # Пытаемся найти название месяца
            for month_name, month_num in MONTHS.items():
                if month_name in clean:
                    parts = clean.replace(month_name, month_num).split()
                    if len(parts) == 3:
                        day, month, year = parts
                        day = day.zfill(2)
                        return f"{day}.{month}.{year}"
                    else:
                        print("⚠ Неполная дата:", clean)
                        return clean
            print("⚠ Неизвестный месяц:", clean)
        case "Декларация":
            clean = CLASS_PRESETS["Декларация"]["regex_date"](date)
        case "Карточка51":
            clean = CLASS_PRESETS["Карточка51"]["regex_date"](date)
        case "ОСВ01":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ58":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ60":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ62":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ66":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ67":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "ОСВ76":
            clean = CLASS_PRESETS["ОСВ"]["regex_date"](date)
        case "Ф1":
            clean = CLASS_PRESETS["Ф1"]["regex_date"](date)
        case "Ф2":
            clean = CLASS_PRESETS["Ф2"]["regex_date"](date)
        case "КП":
            clean = CLASS_PRESETS["КП"]["regex_date"](date)
        case "ЛП":
            clean = CLASS_PRESETS["ЛП"]["regex_date"](date)
        case "КПиЛП":
            clean = CLASS_PRESETS["КПиЛП"]["regex_date"](date)

    return clean


def destructor(filename: str) -> Tuple[str, str]:
    """
    Разделяет имя файла на поддиректорию и сам файл.

    Ожидаемый формат: (поддиректория)_Класс_URL.расширение
    Возвращает:
        subdir: поддиректория без скобок
        filename: всё, что идёт после первого "_"
    """
    # Регулярное выражение: ищет (поддиректория) и остальную часть
    match = re.match(r"^\(*(.+?)\)*_(.+)$", filename)
    if not match:
        raise ValueError(f"Неверный формат имени файла: {filename}")

    subdir = match.group(1).strip()
    remaining_filename = match.group(2).strip()

    return subdir, remaining_filename


def text_slice(text: str, start: float, finish: float):
    """
    Возвращает срез текста, в котором предположительно находится нужная дата документа
    :param text: Текст документа, получается из filename_class.py
    :param start: Эмпирическое значение (приблизительное) - старт среза
    :param finish: Эмпирическое значение (приблизительное) - финиш среза
    :return:
    """
    try:
        # Длина полученного текста
        length = len(text)

        # Подсчет точки начала / конца нужного среза
        start = int((length * start) / 100)
        finish = int((length * finish) / 100)

        # Получаем наш "срез"
        return text[start: finish]
    except Exception as exp:
        print(f"Ошибка, метод text_slice: date_extract.py: {exp}")
        return ""


def best_osv_match(text: str, pattern: re.Pattern) -> re.Match | None:
    """
    Возвращает самое информативное совпадение для ОСВ:
    месяц-месяц > дата-дата > квартал > просто год.
    """
    candidates = list(pattern.finditer(text))
    if not candidates:
        return None

    def score(m: re.Match) -> int:
        g = m.groups()
        has_month_range = bool(g[2] and g[3])  # месяцы с годами (группы 3 и 4)
        has_dd_range = bool(g[4] and g[5])  # dd.mm.yyyy - dd.mm.yyyy
        has_quarter = bool(g[0] and g[1])  # квартал
        has_year_only = bool(g[6] or g[7] or g[8])  # "За 2023 г." и т.п.
        return (
            4 if has_month_range else
            3 if has_dd_range else
            2 if has_quarter else
            1 if has_year_only else
            0
        )

    return max(candidates, key=score)


def extract_date_for_cls(chunk: str, cls: str) -> str:
    """
    Работает теми же правилами, что extraction() для одиночного документа,
    но не трогает OCR/повторный pass – лишнее внутри одного PDF-файла.
    """
    if cls in ("Ф1", "Ф2"):
        chunk = _head(_strip_signature_tails(chunk))

    cfg = CLASS_PRESETS[cls]
    pattern = cfg["regex"]

    # ⬇️ только верхнее окно для Ф1/Ф2
    if cls in ("Ф1", "Ф2"):
        slice_windows = [cfg["slice_first"]]
    else:
        slice_windows = [cfg["slice"]]

    # внутр. поиск cрез + reg-exp — почти 1-в-1 логика extraction()
    def _pick(txt: str) -> re.Match | None:
        return pattern.search(txt)

    for start, finish in slice_windows:
        sliced = text_slice(chunk, start, finish)
        m = _pick(sliced)
        if m:
            raw = m.group(0)
            return date_change(raw, cls)

    # fallback: поиск по всему куску
    m = pattern.search(chunk)
    return date_change(m.group(0), cls) if m else "no-date"


# ────────────────────────────────────────────────────────────────────────────
# ХЕЛПЕРЫ: положи их рядом с остальными вспомогательными функциями
# ────────────────────────────────────────────────────────────────────────────

def prepare_source_text(text: str, cls: str) -> str:
    """
    Для Ф1/Ф2: срезаем хвост с подписями и берём только «голову» документа,
    чтобы не цеплять дату из подписи в конце.
    Для остальных классов — возвращаем как есть.
    """
    t = str(text)
    if cls in ("Ф1", "Ф2"):
        t = _head(_strip_signature_tails(t))
    return t

def get_slice_windows(cls: str, config: dict) -> list[tuple[int, int]]:
    """
    Для Ф1/Ф2 используем только верхнее окно (slice_first).
    Для остальных — стандартный slice из пресета.
    """
    if cls in ("Ф1", "Ф2"):
        return [config["slice_first"]]
    return [config["slice"]]

def _pick_match(pattern: re.Pattern, cls: str, text: str) -> re.Match | None:
    """
    Единая точка поиска: для ОСВ — берём самое информативное совпадение,
    для остальных — обычный pattern.search().
    """
    if cls.startswith("ОСВ"):
        cands = list(pattern.finditer(text))
        if cands:
            return best_osv_match(text, pattern)
        return re.search(r"\b(19\d{2}|20\d{2})\s*г\.?", text, re.I)
    return pattern.search(text)


# ────────────────────────────────────────────────────────────────────────────
# НОВАЯ ВЕРСИЯ extraction()
# ────────────────────────────────────────────────────────────────────────────

def extraction(
        documents: Iterable[str],
        filenames: Iterable[str],
        class_list: Iterable[str]
) -> list[str]:

    renamed: list[str] = []

    for doc, file, cls in zip(documents, filenames, class_list):

        # Спец-случай: один PDF с Ф1+Ф2
        if cls == "Ф1+Ф2":
            f1_chunk, f2_chunk = split_f1_f2(str(doc))
            if not f1_chunk or not f2_chunk:
                print("   !! не удалось найти обе формы (Ф1/Ф2) в тексте")
                renamed.append(f"{cls}(split-error)")
                continue

            date_f1 = extract_date_for_cls(f1_chunk, "Ф1")
            date_f2 = extract_date_for_cls(f2_chunk, "Ф2")

            if date_f1 == "no-date":
                date_f1 = _infer_period_end_generic(f1_chunk)
            if date_f2 == "no-date":
                date_f2 = _infer_period_end_generic(f2_chunk)

            new_name = f"{cls}(Ф1-{date_f1}, Ф2-{date_f2})"
            print(f"   → renamed as: {new_name}")
            renamed.append(new_name)
            continue

        try:
            print("\n".join(doc.splitlines()[:10]))
            print(f"\n─── FILE: {file} | CLS: {cls} ──────────────────────────")
            ext = os.path.splitext(file)[1].lower()

            # 1) выбираем конфиг
            config = CLASS_PRESETS.get(cls) \
                     or (CLASS_PRESETS["ОСВ"] if cls.startswith("ОСВ") else None)
            if not config:
                print("   !! no config for this class")
                renamed.append(f"{cls}(no-config)")
                continue

            pattern = config["regex"]
            slice_windows = get_slice_windows(cls, config)

            # Вспомогательный «поиск по окнам»
            def try_match(source_text: str) -> tuple[str, re.Match | None]:
                """
                Возвращает (sliced_text, match) — первый найденный матч из окон.
                Для ОСВ дополнительно чистим 'счёт 01' и т.п.
                """
                last_slice = ""

                # ОСВ: узкое окно вокруг заголовка
                if cls.startswith("ОСВ"):
                    focus = _osv_focus_window(source_text)
                    if focus:
                        focus_clean = strip_account(focus)
                        m_focus = _pick_match(pattern, cls, focus_clean)
                        if m_focus:
                            return focus_clean, m_focus
                    # если не нашли — идём обычными окнами

                for idx, (start, finish) in enumerate(slice_windows, 1):
                    sliced = text_slice(source_text, start, finish)
                    last_slice = sliced
                    if cls.startswith("ОСВ"):
                        sliced = strip_account(sliced)
                    print(f"   slice-{idx} preview:", repr(sliced[:120]))
                    m = _pick_match(pattern, cls, sliced)
                    print(f"   slice-{idx} match:", "YES" if m else "None")
                    if m:
                        return sliced, m

                return last_slice, None

            # ────────────────────────────────────────────────────────────
            # PASS-1: работаем с уже извлечённым текстом
            # ────────────────────────────────────────────────────────────
            source_text = prepare_source_text(doc, cls)
            sliced, match = try_match(source_text)

            # ────────────────────────────────────────────────────────────
            # PASS-2: если не нашли и это PDF — делаем повторный OCR
            # ────────────────────────────────────────────────────────────
            if not match and ext == ".pdf":
                subdir, _ = destructor(file)
                pdf_path = os.path.join(folder_path, subdir, "Исходники", "pdf")
                try:
                    extracted = PDF_TEXT_EXTRACTOR_FITZ([file], pdf_path).get(file, "")
                except Exception as e:
                    print("   PDF re-extract error:", e)
                    extracted = ""
                if isinstance(extracted, list):
                    extracted = " ".join(extracted)

                print("   ⤷ re-slice phase …")
                source_text_ocr = prepare_source_text(extracted, cls)
                sliced, match = try_match(source_text_ocr)

            # ────────────────────────────────────────────────────────────
            # НОРМАЛИЗАЦИЯ ДАТЫ + ФОЛБЭКИ
            # ────────────────────────────────────────────────────────────
            # Для ОСВ и Ф2 в raw_date отдаём целый «sliced» (он содержит контекст).
            # Для остальных — сам матч.
            raw_date = sliced if (cls.startswith("ОСВ") or cls == "Ф2") \
                else (match.group(0) if match else "no-date")

            date = date_change(raw_date, cls)

            # Умные фолбэки для Ф1/Ф2
            if cls in ("Ф1", "Ф2") and date == "no-date":
                sweep = _fallback_month_year_sweep(str(doc))
                if sweep != "no-date":
                    date = sweep
                else:
                    date = _infer_period_end_generic(str(doc))

            # Спец-фолбэк для Анкеты
            if cls == "Анкета" and date == "no-date":
                date = normalize_anketa_date(sliced)

            print(f"   raw_date: {raw_date!r}  →  normalized: {date}")
            renamed.append(f"{cls}({date})")

        except Exception as exp:
            print(f"   !! exception: {exp}")
            renamed.append(f"{cls}(error)")

    return renamed
