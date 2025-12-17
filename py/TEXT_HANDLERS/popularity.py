import sys
import os

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

def WORD_POPULAR(train_vac):
    """
    Высчитывает популярность слов в контексте одного документа
    :param train_vac: Словарь с парами {'имя_файла': 'список слов'}
    :return result: Новый словарь с парами {'имя_файла': словарь с парами {'слово': 'коэффициент популярности'}}
    """
    # Новый словарь для хранения результатов
    result = {}

    for file, words in train_vac.items():
        inner = {}
        # Используем `set` вместо списка
        seen_words = set()

        for word in words:
            if word in seen_words:
                # Пропускаем повторное слово
                continue
            else:
                print(words.count(word))
                # Записываем результат подсчета популярности слова
                inner[word] = str(words.count(word) / len(words))
                # Заносим слово в список, чтобы в дальнейшем его не обрабатывать
                seen_words.add(word)

        # Записываем результат в новый словарь
        result[file] = inner

    # Возвращаем новый словарь без изменения исходных данных
    return result
