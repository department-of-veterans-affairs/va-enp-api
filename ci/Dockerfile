FROM python:3.12-alpine3.20


ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN pip install --upgrade pip
RUN pip install poetry==1.8.3

WORKDIR /app

COPY . .

RUN poetry install --no-root --with static_tools,test && rm -rf $POETRY_CACHE_DIR
