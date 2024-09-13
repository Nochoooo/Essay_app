FROM python:3.10-slim

WORKDIR /ML_service

COPY ./requirements.txt /ML_service/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir kafka-python==2.0.2

COPY . /ML_service

CMD ["uvicorn", "model:app", "--host", "0.0.0.0", "--port", "8001"]


