from FILE_HANDLERS.EXTRACORS.words_extr import WORD_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.pdfs_extr import PDF_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.excels_extr import EXCEL_TEXT_EXTRACTOR
from FILE_HANDLERS.EXTRACORS.imgs_extr import IMAGE_TEXT_EXTRACTOR
from TEXT_HANDLERS.VECTORIZATION.tf_idf import TF_IDF_LEARNING
from MACHINE_LEARNING.logistic_regr import LOG_REG_LEARNING
import sys
import os

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

def LEARNING(WORD_FILES, WORD_REPOS_DIR,
             PDF_FILES, PDF_REPOS_DIR,
             EXCEL_FILES, EXCEL_REPOS_DIR,
             IMG_FILES, IMG_REPOS_DIR,):
    """
    Запускает обучение на полученных на вход данных

    :param WORD_FILES: Массив названий файлов в директории repos/repos_learn/word
    :param WORD_REPOS_DIR: Массив названий файлов в директории repos/repos_predict/word
    :param PDF_FILES: Массив названий файлов в директории repos/repos_learn/pdf
    :param PDF_REPOS_DIR: Массив названий файлов в директории repos/repos_predict/pdf
    :param EXCEL_FILES: Массив названий файлов в директории repos/repos_learn/excel
    :param EXCEL_REPOS_DIR: Массив названий файлов в директории repos/repos_predict/excel
    :param IMG_FILES: Массив названий файлов в директории repos/repos_learn/img
    :param IMG_REPOS_DIR: Массив названий файлов в директории repos/repos_predict/img
    :return: None
    """

    # Извлекаем текст из word - файлов
    EXTRACTED_WORD_TEXTS = WORD_TEXT_EXTRACTOR(WORD_FILES, WORD_REPOS_DIR)

    # Извлекаем текст из pdf - файлов
    EXTRACTED_PDF_TEXTS = PDF_TEXT_EXTRACTOR(PDF_FILES, PDF_REPOS_DIR)

    # Извлекаем текст из excel - файлов
    EXTRACTED_EXCEL_TEXTS = EXCEL_TEXT_EXTRACTOR(EXCEL_FILES, EXCEL_REPOS_DIR)

    # Извлекаем текст из img - файлов
    EXTRACTED_IMG_TEXTS = IMAGE_TEXT_EXTRACTOR(IMG_FILES, IMG_REPOS_DIR)

    LEARNING_DATA = {
        **EXTRACTED_WORD_TEXTS,
        **EXTRACTED_PDF_TEXTS,
        **EXTRACTED_IMG_TEXTS,
        **EXTRACTED_EXCEL_TEXTS
    }

    x_train, y_train = TF_IDF_LEARNING(LEARNING_DATA, True)

    LOG_REG_LEARNING(x_train, y_train)
