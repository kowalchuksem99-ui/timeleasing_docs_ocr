import re
import sys
import os

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))


def IS_VALID(text, threshold):
    """
    Определяет, является ли текст валидным русским текстом.
    Если доля кириллических символов меньше threshold, текст считается "мусорным".

    :param text: Текс для анализа
    :param threshold: Минимальная доля символов в тексте, которые должны быть кириллическими.
    :return:
    """

    if not text:
        return False
    # Ищем все кириллические символы (включая Ёё)
    cyrillic_chars = re.findall(r'[А-Яа-яЁё]', text)
    # Коэффициент отражающий степень содержания "мешанины в тексте"
    ratio = len(cyrillic_chars) / len(text)
    return ratio >= threshold
