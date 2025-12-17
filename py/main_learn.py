import os
from joblib import load
from learning import LEARNING
from classification import PREDICT
import sys

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

###################################################################
# Пути до директорий исполняющего файла и файлов для сканирования #
###################################################################

# Путь до директории, из которой скрипт ведет работу
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Загрузка Модели
MODEL = load(r"C:\Users\kovalchuk\PycharmProjects\DOCS_ANALYZE\py\CORE_VECTOR\26.03.2025\core_pipeline.joblib")

# Обучение
WORD_REPOS_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_learn', 'word')  # Директория repos/repos_learn/word
PDF_REPOS_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_learn', 'pdf')  # Директория repos/repos_learn/pdf
IMG_REPOS_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_learn', 'img')  # Директория repos/repos_learn/img
EXCEL_REPOS_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_learn', 'excel')  # Директория repos/repos_learn/excel

# Классификация
WORD_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict',
                                'word')  # Директория repos/repos_predict/word
PDF_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'pdf')  # Директория repos/repos_predict/pdf
IMG_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict', 'img')  # Директория repos/repos_predict/img
EXCEL_PREDICT_DIR = os.path.join(SCRIPT_DIR, '..', 'repos', 'repos_predict',
                                 'excel')  # Директория repos/repos_learn/excel

##############################################################
# Переменные для списков с названиями файлов на сканирование #
##############################################################

# Обучение
WORD_FILES = os.listdir(WORD_REPOS_DIR)  # Массив названий файлов в директории repos/repos_learn/word
PDF_FILES = os.listdir(PDF_REPOS_DIR)  # Массив названий файлов в директории repos/repos_learn/pdf
IMG_FILES = os.listdir(IMG_REPOS_DIR)  # Массив названий файлов в директории repos/repos_learn/img
EXCEL_FILES = os.listdir(EXCEL_REPOS_DIR)  # Массив названий файлов в директории repos/repos_learn/excel

# Классификация
WORD_FILES_PREDICT = os.listdir(WORD_PREDICT_DIR)  # Массив названий файлов в директории repos/repos_predict/word
PDF_FILES_PREDICT = os.listdir(PDF_PREDICT_DIR)  # Массив названий файлов в директории repos/repos_predict/pdf
IMG_FILES_PREDICT = os.listdir(IMG_PREDICT_DIR)  # Массив названий файлов в директории repos/repos_predict/img
EXCEL_FILES_PREDICT = os.listdir(EXCEL_PREDICT_DIR)  # Массив названий файлов в директории repos/repos_predict/excel

#################
# ОСНОВНОЕ ТЕЛО #
#################

############
# LEARNING #
############

LEARNING(WORD_FILES, WORD_REPOS_DIR,
         PDF_FILES, PDF_REPOS_DIR,
         EXCEL_FILES, EXCEL_REPOS_DIR,
         IMG_FILES, IMG_REPOS_DIR)

###########
# PREDICT #
###########

# PREDICT(WORD_FILES_PREDICT, WORD_PREDICT_DIR,
#         PDF_FILES_PREDICT, PDF_PREDICT_DIR,
#         EXCEL_FILES_PREDICT, EXCEL_PREDICT_DIR,
#         IMG_FILES_PREDICT, IMG_PREDICT_DIR,
#         MODEL)
