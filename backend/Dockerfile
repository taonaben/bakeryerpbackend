FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && apt-get clean

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput || true

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
