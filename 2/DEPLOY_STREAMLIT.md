# Публикация приложения в Streamlit Community Cloud

## 1. Загрузить проект в GitHub

В репозитории должны лежать файлы из этой папки:

```text
streamlit_app.py
app.py
data_utils.py
geo_utils.py
requirements.txt
.streamlit/config.toml
data/sample_dialects.csv
data/data_template.csv
```

## 2. Создать приложение в Streamlit

1. Откройте Streamlit Community Cloud.
2. Нажмите **Create app**.
3. Выберите репозиторий и ветку `main`.
4. В поле **Main file path** укажите:

```text
streamlit_app.py
```

5. В **Advanced settings** выберите Python 3.12 или 3.11.
6. В поле **Secrets** при необходимости вставьте:

```toml
DATA_CSV_URL = "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=0"
REMOTE_TABLE_EDIT_URL = "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit"
BOUNDARY_GEOJSON_URL = ""
```

7. Нажмите **Deploy**.

## 3. Локальный запуск

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

После запуска Streamlit откроет приложение в браузере.

## 4. Проверка перед публикацией

```bash
python -m py_compile app.py data_utils.py geo_utils.py streamlit_app.py
python -m streamlit run streamlit_app.py
```

Если таблица Google Sheets ещё не подключена, приложение откроется на демо-данных из `data/sample_dialects.csv`.
