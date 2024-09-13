FROM python:3.10-slim

WORKDIR /ui_service
COPY ./requirements.txt /ui_service/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir kafka-python==2.0.2


COPY . /ui_service

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]