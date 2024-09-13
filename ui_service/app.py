from fastapi import FastAPI, Request, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from loguru import logger
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from werkzeug.utils import secure_filename
import os
import json
from database import Database


app = FastAPI()

# Инициализация Kafka producer и consumer
kafka_server = os.environ.get('KAFKA_SERVER', 'kafka:9092')
kafka_producer_topic = os.environ.get('KAFKA_PRODUCER_TOPIC', 'predict_requests')
kafka_consumer_topic = os.environ.get('KAFKA_CONSUMER_TOPIC', 'predict_responses')
producer = KafkaProducer(bootstrap_servers=kafka_server, api_version=(0,11,5), value_serializer=lambda v: json.dumps(v).encode('utf-8'))
consumer = KafkaConsumer(kafka_consumer_topic, bootstrap_servers=kafka_server, api_version=(0,11,5), value_deserializer=lambda v: json.loads(v.decode('utf-8')))



# Путь к директории для загруженных файлов
app_dir = os.path.dirname(__file__)

# Создание папки static, если она не существует
static_folder = os.path.join(app_dir, 'static')
os.makedirs(static_folder, exist_ok=True)

# Путь к директории для загруженных файлов
UPLOAD_FOLDER = os.path.join(static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_folder), name="static")


# Инициализация объектов базы данных
database = Database()

templates = Jinja2Templates(directory="templates")

def basename_filter(value):
    return os.path.basename(value)

templates.env.filters['basename'] = basename_filter


def get_unique_filename(upload_folder, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(upload_folder, unique_filename)):
        unique_filename = f"{base}_{counter}{ext}"
        counter += 1
    return unique_filename



@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/")
async def handle_form(
    author: str = Form(...), 
    essay_file: UploadFile = Form(...)
):
    database.create_essays_table_if_not_exists()
    
    if not essay_file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Файл должен иметь формат .txt")
    

    # Читаем содержимое файла
    try:
        content = await essay_file.read()  
        content = content.decode('utf-8')  
    except UnicodeDecodeError as e:
        logger.error(f"Ошибка декодирования файла: {e}")
        raise HTTPException(status_code=400, detail="Ошибка декодирования файла.")
    
    if not content:
        logger.error("Файл пустой или не удалось прочитать содержимое файла.")
        raise HTTPException(status_code=400, detail="Файл пустой или не удалось прочитать содержимое файла.")
    
    # Сохранение файла
    unique_filename = get_unique_filename(UPLOAD_FOLDER, secure_filename(essay_file.filename))
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    if os.path.exists(file_path):
        logger.info(f"Файл успешно сохранен по пути: {file_path}")
    else:
        logger.error(f"Не удалось сохранить файл по пути: {file_path}")
    
    # Отправка данных в Kafka
    try:
        producer.send(kafka_producer_topic, {'content': [content], 'file_path': file_path})
    except KafkaError as e:
        logger.error(f"Ошибка отправки сообщения в Kafka: {e}")
        raise HTTPException(status_code=500, detail="Ошибка отправки данных на ML сервис.")


    # Получение результата предсказания из Kafka
    try:
        for msg in consumer:
            result = msg.value
            if 'score' in result and result['file_path'] == file_path:
                score = result['score']
    # Сохранение данных в базу данных
                database.insert_data_into_essays(author, file_path, score)
                logger.info(f"Оценка {score} успешно сохранена в базе данных для файла {file_path}.")
                break
    except KafkaError as e:
        logger.error(f"Ошибка при получении ответа из Kafka: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении ответа от ML сервиса.")
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/view", response_class=HTMLResponse)
async def view(request: Request):
    essays = database.get_all_essays()
    if essays is None:
        raise HTTPException(status_code=500, detail="Ошибка при получении данных из базы.")
    return templates.TemplateResponse("view.html", {"request": request, "essays": essays})

@app.post("/delete")
async def delete(data: dict):
    ids_to_delete = data['ids']
    ids_to_delete = [int(i) for i in ids_to_delete]
    if database.delete_essays(ids_to_delete):
        return {}
    raise HTTPException(status_code=500, detail="Ошибка при удалении записей.")

@app.post("/update_score")
async def update_score(data: dict):
    essay_id = data['id']
    new_score = data['score']
    try:
        new_score = int(new_score)
        if not (1 <= new_score <= 6):
            raise ValueError('Недопустимая оценка.')
    except ValueError as e:
        logger.error(f"Ошибка проверки: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    if database.update_essay_score(essay_id, new_score):
        return {}
    raise HTTPException(status_code=500, detail="Ошибка при обновлении оценки.")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, debug=True)
