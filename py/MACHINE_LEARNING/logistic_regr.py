import joblib
import os
import sys
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer
from py.FILE_HANDLERS.OTHER.date_folders import TIME_FOLDERS
from tqdm import tqdm
from time import sleep

# Добавляем папку py в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'py'))

def LOG_REG_LEARNING(documents, y):
    """
    Подбирает параметры как TF-IDF-векторизатора, так и LogisticRegression
    с помощью Pipeline + GridSearchCV. Добавлен прогресс-бар через tqdm.
    """

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer()),
        ('clf', LogisticRegression())
    ])

    param_grid = [

        # Блок 1: L1-регуляризация, только solver = liblinear
        {
            'tfidf__min_df': [2, 3],
            'tfidf__max_df': [0.8, 1.0],
            'tfidf__max_features': [5000, 10000],
            'tfidf__ngram_range': [(1, 1), (1, 2)],
            'clf__penalty': ['l1'],
            'clf__C': [0.1, 1, 10],
            'clf__solver': ['liblinear'],
            'clf__max_iter': [300],
            'clf__class_weight': ['balanced', None],
        },

        # Блок 2: L2-регуляризация, solver = liblinear
        {
            'tfidf__min_df': [2, 3],
            'tfidf__max_df': [0.8, 1.0],
            'tfidf__max_features': [5000, 10000],
            'tfidf__ngram_range': [(1, 1), (1, 2)],
            'clf__penalty': ['l2'],
            'clf__C': [0.1, 1, 10],
            'clf__solver': ['liblinear'],
            'clf__dual': [False],  # важно!
            'clf__max_iter': [300],
            'clf__class_weight': ['balanced', None],
        },

        # Блок 3: L2-регуляризация, solver = lbfgs (более точный, но медленный)
        {
            'tfidf__min_df': [2],
            'tfidf__max_df': [0.8],
            'tfidf__max_features': [8000, 10000],
            'tfidf__ngram_range': [(1, 1), (1, 2)],
            'clf__penalty': ['l2'],
            'clf__C': [1, 10, 100],
            'clf__solver': ['lbfgs'],
            'clf__max_iter': [300],
            'clf__class_weight': ['balanced', None],
        }

    ]

    search = GridSearchCV(
        pipeline,
        param_grid=param_grid,
        scoring='accuracy',
        cv=5,
        n_jobs=-1,
        verbose=10  # <-- Показывает прогресс по fold'ам
    )

    print("🚀 Начинаем подбор параметров...")

    # Покажем фейковый прогресс-бар, пока работает .fit()
    # Примерное число комбинаций: 108 (смотри предыдущий расчёт)
    with tqdm(total=1, desc="GridSearchCV обучение", bar_format="{l_bar}{bar}| {elapsed}") as pbar:
        search.fit(documents, y)
        pbar.update(1)

    best_pipeline = search.best_estimator_
    print("✅ Лучшие гиперпараметры:", search.best_params_)
    print("📈 Лучший score (accuracy):", search.best_score_)

    path_for_mv = r"C:\Users\kovalchuk\PycharmProjects\DOCS_ANALYZE\py\CORE_VECTOR"
    joblib.dump(best_pipeline, filename=os.path.join(TIME_FOLDERS(path_for_mv), "core_pipeline.joblib"))

    train_preds = best_pipeline.predict(documents)
    print("📦 Предсказания на обучающей выборке:", train_preds)
    print("🧾 Классы модели:", best_pipeline.named_steps['clf'].classes_)
