from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from loguru import logger
from psycopg2 import DatabaseError
import os

app = Flask(__name__)


def db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='Essay',
        user='postgres',
        password='cyrva289',
        port='5432',
    )


@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            author = request.form['author']
            essay_file = request.files['essay_file'].read().decode('utf-8')
            score = 1.0
            conn = db_connection()
            cur = conn.cursor()
            cur.execute('INSERT INTO essays (author, content, score) VALUES (%s, %s, %s)', (author, essay_file, score))
            conn.commit()
            return redirect(url_for('index'))
    except DatabaseError as db_error:
        logger.error(f"Database error during insertion: {db_error}")
        if conn:
            conn.rollback()
        return "Ошибка при добавлении данных в базу данных.", 500
    except UnicodeDecodeError as uni_error:
        logger.error(f"Unicode decode error: {uni_error}")
        return "Ошибка декодирования файла.", 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if 'cur' in locals() and cur is not None:
            cur.close()
        if 'conn' in locals() and conn is not None:
            conn.close()
    return render_template('index.html')


@app.route('/view', methods=['GET'])
def view():
    conn = None
    cur = None
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM essays')
        essays = cur.fetchall()
        essays_data = [{'id': essay[0], 'author': essay[1], 'content': essay[2], 'score': essay[3]} for essay in essays]
        return render_template('view.html', essays=essays_data)
    except DatabaseError as db_error:
        logger.error(f"Database error during fetching essays: {db_error}")
        return "Ошибка при получении данных из базы.", 500
    except Exception as e:
        logger.error(f"Unexpected error during fetching essays: {e}")
        return "Неизвестная ошибка сервера.", 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/delete', methods=['POST'])
def delete():
    data = request.get_json()
    ids_to_delete = data['ids']
    # Преобразуем все элементы списка в числа
    ids_to_delete = [int(i) for i in ids_to_delete]
    conn = None
    cur = None
    try:
        conn = db_connection()
        cur = conn.cursor()
        # Используем список чисел для запроса
        cur.execute('DELETE FROM essays WHERE id = ANY(%s)', (ids_to_delete,))
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
        if cur:
            cur.close()
        if conn:
            conn.close()
    return '', 204


@app.route('/update_score', methods=['POST'])
def update_score():
    data = request.get_json()
    essay_id = data['id']
    new_score = data['score']

    # Проверяем, что new_score является числом и находится в нужном диапазоне
    try:
        new_score = float(new_score)
        if not (0 <= new_score <= 10):
            raise ValueError('Недопустимая оценка.')
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return str(e), 400  # Возвращаем ошибку клиенту

    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE essays SET score = %s WHERE id = %s', (new_score, essay_id))
        conn.commit()
    except psycopg2.DatabaseError as e:
        logger.error(f"Database error: {e}")
        conn.rollback()  # Откатываем изменения в случае ошибки
        return str(e), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return str(e), 500
    finally:
        cur.close()
        conn.close()
    return '', 204


if __name__ == '__main__':
    app.run(debug=True)
