# basic starting point to run the app in a container
FROM python:3.12-alpine3.20

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

RUN adduser -h /app -D vanotify

RUN pip install --upgrade pip 
RUN pip install poetry==1.8.3

USER vanotify

COPY pyproject.toml poetry.lock /app/

RUN poetry install --no-root --with static_tools,test,mkdocs && rm -rf $POETRY_CACHE_DIR


COPY docs /app/docs
COPY mkdocs.yml /app/mkdocs.yml
COPY app /app/app
COPY scripts /app/scripts

RUN poetry run mkdocs build


