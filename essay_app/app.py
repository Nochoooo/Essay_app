from flask import Flask, render_template, request, redirect, url_for
from loguru import logger
from werkzeug.utils import secure_filename
import os
from database import Database
from model import EssayModel

# Инициализация Flask приложения
app = Flask(__name__)

# Путь к директории для загруженных файлов
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')

# Установка папки для загруженных файлов в конфигурации Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Создание директории для загруженных файлов, если она не существует
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Инициализация объектов базы данных и модели
database = Database()
essay_model = EssayModel()

# Главная страница и обработка формы
@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            database.create_essays_table_if_not_exists()
            
            # Получаем данные из формы
            author = request.form['author']
            essay_file = request.files['essay_file']
            
            if not essay_file.filename.endswith('.txt'):
                return "Файл должен иметь формат .txt", 400
            
            # Читаем содержимое файла
            try:
                content = essay_file.read().decode('utf-8')
            except UnicodeDecodeError as e:
                logger.error(f"Ошибка декодирования файла: {e}")
                return "Ошибка декодирования файла.", 400
            
            if not content:
                logger.error("Файл пустой или не удалось прочитать содержимое файла.")
                return "Файл пустой или не удалось прочитать содержимое файла.", 400

            # Сохраняем файл на сервере
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], essay_file.filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Файл успешно сохранен по пути: {file_path}")
            
            # Предсказание оценки
            score = essay_model.predict_score([content])
            logger.info(f"Предсказанная оценка: {score}")
            
            if all([author, file_path, score]):
                database.insert_data_into_essays(author, essay_file.filename, score)
            
            return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return "Произошла ошибка на сервере.", 500
    
    return render_template('index.html')

# Обработчик маршрута для отображения списка эссе
@app.route('/view', methods=['GET'])
def view():
    essays = database.get_all_essays()
    if essays is None:
        return "Ошибка при получении данных из базы.", 500
    return render_template('view.html', essays=essays)

# Обработчик маршрута для удаления выбранных эссе
@app.route('/delete', methods=['POST'])
def delete():
    data = request.get_json()
    ids_to_delete = data['ids']
    ids_to_delete = [int(i) for i in ids_to_delete]
    if database.delete_essays(ids_to_delete):
        return '', 204
    return "Ошибка при удалении записей.", 500

# Обработчик маршрута для обновления оценки эссе
@app.route('/update_score', methods=['POST'])
def update_score():
    data = request.get_json()
    essay_id = data['id']
    new_score = data['score']
    try:
        new_score = float(new_score)
        if not (1 <= new_score <= 6):
            raise ValueError('Недопустимая оценка.')
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return str(e), 400

    if database.update_essay_score(essay_id, new_score):
        return '', 204
    return "Ошибка при обновлении оценки.", 500

# Точка входа для запуска приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
