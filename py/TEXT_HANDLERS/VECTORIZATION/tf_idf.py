import os
import pandas as pd
import sys

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

def get_label_from_filename(filename):
    """
    Извлекает класс документа из имени файла. Используется только при обучении.
    Предполагаем формат: <Класс>_<что-то>.<расширение>

    Пример:
      "Анкета_2.pdf" -> "Анкета"
      "ОСВ_12.xlsx" -> "ОСВ"
    :param filename: список названий файлов
    :return label: класс документа
    """
    # Удаляем расширение (".pdf", ".xlsx", ".docx", ".doc", "img")
    base = os.path.splitext(filename)[0]  # "файл_1" из "файл_1.pdf"
    # Берём всё до первого '_' и определяем как класс документа
    parts = base.split("_", maxsplit=1)
    label = parts[0]  # " 'файл' <--- _1.pdf"
    return label


def TF_IDF_LEARNING(EXTRACTED_TEXT, save_excel=False, x_file="x.xlsx", y_file="y.xlsx"):
    """
    Превращает тексты в TF-IDF - матрицу,
    и возвращает (tfidf_matrix, labels), где labels[i] - метка класса
    документа i. Метод используется для обучающей выборки.

    EXTRACTED_TEXT: {
         "имя_файла": ["лемма1", "лемма2", ...],
         "имя_файла2": [...],
         ...
    }

    :param EXTRACTED_TEXT: выгруженный из файлов текст.

    :return: (x, y, vectorizer)
       - x: матрица TF-IDF размера [число_документов x число_терминов]
       - y: список меток классов, извлечённых из имени файла,
                 в том же порядке, что строки tfidf_matrix
       - vectorizer: векторизатор (настроенный)
    """
    # Список с текстами из документов
    documents = []
    # Названия документов из обучающей выборки
    filenames = []
    for filename, lemmas in EXTRACTED_TEXT.items():
        # Соединяем все леммы из списка в одну строку
        text_str = " ".join(lemmas)
        documents.append(text_str)
        filenames.append(filename)

    try:
        x = documents
        y = [get_label_from_filename(fn) for fn in filenames]
    except Exception as e:
        print(f"Недостаточно файлов для обучающей выборки: {e}")
        return None, None

    if save_excel:
        # Сохраним x и y в два отдельных Excel файла
        # Например, можно сохранить x вместе с названием файла
        df_x = pd.DataFrame({"filename": filenames, "text": x})
        df_y = pd.DataFrame({"filename": filenames, "label": y})
        df_x.to_excel(x_file, index=False)
        df_y.to_excel(y_file, index=False)
        print(f"Данные сохранены: {x_file} и {y_file}")

    return x, y


def TF_IDF_PREDICT(EXTRACTED_TEXT, vectorizer):
    """
    Превращает тексты в TF-IDF - матрицу и возвращает tfidf_matrix.
    Метод используется для классифицируемых данных.

    EXTRACTED_TEXT: {"имя_файла_1": ["лемма_1", "лемма_2", ...],
                     "имя_файла_2": ["лемма_1", "лемма_2", ...],
                     ...
    }

    :param vectorizer: векторизатор (настроенный еще на этапе обучения)
    :param EXTRACTED_TEXT: извлеченный из файла текст
    :return: X_new: текст классифицируемого файла в формате TF-IDF матрицы
    """
    # Список с текстами из документов
    documents = []
    for lemmas in EXTRACTED_TEXT.values():
        # Соединяем все леммы из списка в одну строку
        text_str = " ".join(lemmas)
        # Помещаем полученный текст в список documents
        documents.append(text_str)
    # Формируем контрольную выборку
    x_new = vectorizer.transform(documents)
    return x_new
