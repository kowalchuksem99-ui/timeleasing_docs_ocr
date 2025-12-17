from FILE_HANDLERS.EXTRACORS.words_extr import WORD_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.pdfs_extr import PDF_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.excels_extr import EXCEL_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.imgs_extr import IMAGE_TEXT_EXTRACTOR
from FILE_HANDLERS.filename_class import FILE_CLASS_RENAME
from FILE_HANDLERS.date_extract import extraction
import joblib
import sys
import os

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))


def PREDICT(WORD_FILES_PREDICT, WORD_PREDICT_DIR,
            PDF_FILES_PREDICT, PDF_PREDICT_DIR,
            EXCEL_FILES_PREDICT, EXCEL_PREDICT_DIR,
            IMG_FILES_PREDICT, IMG_PREDICT_DIR,
            PIPELINE_FILE=r'core_pipeline.joblib'):
    """
    Запускает классификацию на полученных на вход данных

    :param PIPELINE_FILE: Ссылка на файл модели + векторизатора
    :param WORD_FILES_PREDICT: Массив названий файлов в директории repos/repos_learn/word
    :param WORD_PREDICT_DIR: Массив названий файлов в директории repos/repos_predict/word
    :param PDF_FILES_PREDICT: Массив названий файлов в директории repos/repos_learn/pdf
    :param PDF_PREDICT_DIR: Массив названий файлов в директории repos/repos_predict/pdf
    :param EXCEL_FILES_PREDICT: Массив названий файлов в директории repos/repos_learn/excel
    :param EXCEL_PREDICT_DIR: Массив названий файлов в директории repos/repos_predict/excel
    :param IMG_FILES_PREDICT: Массив названий файлов в директории repos/repos_learn/img
    :param IMG_PREDICT_DIR: Массив названий файлов в директории repos/repos_predict/img
    :return:
    """
    # Извлекаем текст из word - файлов
    EXTRACTED_WORD_TEXTS_PREDICT = WORD_TEXT_EXTRACTOR(WORD_FILES_PREDICT, WORD_PREDICT_DIR)

    # Извлекаем текст из pdf - файлов
    EXTRACTED_PDF_TEXTS_PREDICT = PDF_TEXT_EXTRACTOR(PDF_FILES_PREDICT, PDF_PREDICT_DIR)

    # Извлекаем текст из excel - файлов
    EXTRACTED_EXCEL_TEXTS_PREDICT = EXCEL_TEXT_EXTRACTOR(EXCEL_FILES_PREDICT, EXCEL_PREDICT_DIR)

    # Извлекаем текст из img - файлов
    EXTRACTED_IMG_TEXTS_PREDICT = IMAGE_TEXT_EXTRACTOR(IMG_FILES_PREDICT, IMG_PREDICT_DIR)

    PREDICT_DATA = {
        **EXTRACTED_WORD_TEXTS_PREDICT,
        **EXTRACTED_PDF_TEXTS_PREDICT,
        **EXTRACTED_IMG_TEXTS_PREDICT,
        **EXTRACTED_EXCEL_TEXTS_PREDICT
    }

    # Для pipeline требуется список текстов, поэтому собираем их и формируем список документов и имён файлов
    documents = []
    filenames = []
    clasess = [
        "Анкета",
        "Выписка",
        "Договор аренды или свидетельство о праве собственности",
        "Декларация",
        "Договор(с заказчиком)",
        "Кредитный портфель",
        "Кредитный и лизинговый портфель",
        "Карточка 51 счёта",
        "Лизинговый портфель",
        "ОСВ 01",
        "ОСВ 58",
        "ОСВ 60",
        "ОСВ 62",
        "ОСВ 66",
        "ОСВ 67",
        "ОСВ 76",
        "Паспорт",
        "Прочее",
        "Решение",
        "Устав",
        "Форма №1",
        "Форма №1 + Форма №2",
        "Форма №2"
    ]

    for filename, lemmas in PREDICT_DATA.items():
        # Если текст представлен списком лемм, объединяем их в одну строку
        text_str = " ".join(lemmas) if isinstance(lemmas, list) else lemmas
        documents.append(text_str)
        filenames.append(filename)


    if filenames:
        # Загружаем готовый pipeline
        pipeline = joblib.load(PIPELINE_FILE)
        # Выполняем предсказание. Pipeline сам проведёт преобразов ание текста и классификацию.
        predictions = pipeline.predict(documents)

        renamed_filenames = extraction(documents, filenames, predictions) # <- До этой строчки нужен скрипт разъединения
        probabilities = pipeline.predict_proba(documents)

        #print("\nПредсказания для новых документов:", predictions)

        for cls, probs in zip(clasess, probabilities.T):
            #print(f"\nКласс «{cls}»")
            for filename, p in zip(filenames, probs):
                print("") #f"  {filename}: {round(p * 100):.4f}%"

        # Если требуется переименование файлов по результатам классификации, вызываем соответствующую функцию.
        FILE_CLASS_RENAME(PREDICT_DATA, documents, filenames, renamed_filenames, PDF_PREDICT_DIR, WORD_PREDICT_DIR, EXCEL_PREDICT_DIR, IMG_PREDICT_DIR)
