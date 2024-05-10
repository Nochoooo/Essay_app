from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from loguru import logger
from psycopg2 import DatabaseError
import os

# Инициализация Flask приложения
app = Flask(__name__)


# Функция для подключения к базе данных из переменных окружения
def db_connection():
    try:
        db_password = os.environ.get('POSTGRES_PASSWORD')
        db_host = os.environ.get('DB_HOST')
        db_port = os.environ.get('DB_PORT')
        db_name = os.environ.get('DB_NAME')
        db_user = os.environ.get('DB_USER')
        return psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)

    # Логируем ошибку при неудачной попытке извлечения параметров
    except Exception as e:
        logger.error(f"Error retrieving DB connection parameters from ConfigMap: {str(e)}")
        return None


# Функция для создания таблицы в базе данных, если она еще не существует
def create_essays_table_if_not_exists():
    # Инициализируем переменные соединения и курсора
    conn = None
    cursor = None
    try:
        conn = db_connection()
        cursor = conn.cursor()
        # Выполняем SQL запрос
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS essays (
                id SERIAL PRIMARY KEY,
                author VARCHAR(100) NOT NULL,
                content TEXT NOT NULL,
                score REAL NOT NULL
            )
        """)
        conn.commit()  # Фиксируем изменения в БД
    # Логируем ошибку при неудачной попытке создания таблицы
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def insert_data_into_essays(author_data, content_data, score_data):
    conn = None
    cursor = None
    try:
        conn = db_connection()
        cursor = conn.cursor()
        # Выполняем запрос на вставку данных
        cursor.execute("INSERT INTO essays (author, content, score) VALUES (%s, %s, %s)",
                       (author_data, content_data, score_data))
        conn.commit()  # Фиксируем изменения в БД
    except DatabaseError as db_error:
        logger.error(f"Database error insert data: {db_error}")
        if conn:
            conn.rollback()
        return "Ошибка при добавлении записи.", 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            create_essays_table_if_not_exists()  # Создаем таблицу 'essays', если она не существует
            # Получаем данные из формы
            author = request.form['author']
            content = request.files['essay_file'].read().decode('utf-8')
            score = 1.0
            insert_data_into_essays(author, content, score)  # Добавляем данные в базу
            return redirect(url_for('index'))
    except UnicodeDecodeError as uni_error:
        logger.error(f"Unicode decode error: {uni_error}")
        return "Ошибка декодирования файла.", 400
    return render_template('index.html')


# Обработчик маршрута для отображения списка эссе
@app.route('/view', methods=['GET'])
def view():
    conn = None
    cursor = None
    try:
        conn = db_connection()
        cursor = conn.cursor()
        # Выполняем SQL запрос для получения всех данных из базы
        cursor.execute("SELECT * FROM essays")
        essays = cursor.fetchall()
        # Преобразуем полученные данные в список словарей
        essays_data = [{'id': essay[0], 'author': essay[1], 'content': essay[2], 'score': essay[3]} for essay in
                       essays]
        # Отображаем страницу с данными эссе
        return render_template('view.html', essays=essays_data)
    except DatabaseError as db_error:
        logger.error(f"Database error during fetching essays: {db_error}")
        return "Ошибка при получении данных из базы.", 500
    # Логируем любые неожиданные ошибки
    except Exception as e:
        logger.error(f"Unexpected error during fetching essays: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Обработчик маршрута для удаления выбранных эссе
@app.route('/delete', methods=['POST'])
def delete():
    # Получаем данные в формате JSON из запроса
    data = request.get_json()
    # Извлекаем идентификаторы для удаления из полученных данных
    ids_to_delete = data['ids']
    # Преобразуем идентификаторы в числа для безопасного использования в SQL-запросе
    ids_to_delete = [int(i) for i in ids_to_delete]
    conn = None
    cursor = None
    try:
        conn = db_connection()
        cursor = conn.cursor()
        # Выполняем SQL запрос для удаления эссе по идентификаторам
        cursor.execute("DELETE FROM essays WHERE id = ANY(%s)", (ids_to_delete,))
        conn.commit()
    except DatabaseError as db_error:
        logger.error(f"Database error during deletion: {db_error}")
        if conn:
            conn.rollback()
        return "Ошибка при удалении записей.", 500
    except ValueError as val_error:
        logger.error(f"Value error during deletion: {val_error}")
        return "Недопустимый формат идентификатора.", 400
    except Exception as e:
        logger.error(f"Unexpected error during deletion: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return '', 204


@app.route('/update_score', methods=['POST'])
def update_score():
    conn = None
    cursor = None
    data = request.get_json()
    # Извлекаем ID эссе и новую оценку из полученных данных
    essay_id = data['id']
    new_score = data['score']
    # Проверяем, что new_score является числом и находится в допустимом диапазон
    try:
        new_score = float(new_score)
        if not (0 <= new_score <= 10):
            raise ValueError('Недопустимая оценка.')
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return str(e), 400

    try:
        conn = db_connection()
        cursor = conn.cursor()
        # Выполняем SQL запрос для обновления оценки эссе
        cursor.execute("UPDATE essays SET score = %s WHERE id = %s", (new_score, essay_id))
        conn.commit()
    except psycopg2.DatabaseError as e:
        logger.error(f"Database error: {e}")
        conn.rollback()  # Откатываем изменения в случае ошибки
        return str(e), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return str(e), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return '', 204


# Точка входа для запуска приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
# Запускаем Flask-сервер на 0.0.0.0, чтобы он был доступен на всех интерфейсах
# Устанавливаем порт 5000 и включаем режим отладки для упрощения разработки
