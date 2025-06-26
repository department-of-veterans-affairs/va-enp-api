# Builder stage
# This stage is used to install dependencies
# We use a multi-stage build to keep the final image size small
FROM python:3.13-alpine3.21 AS builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_HOME="/opt/poetry" \
    POETRY_VERSION=2.1.3

ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock /app/

ARG POETRY_ARGS

# install system dependencies
RUN apk add --no-cache --virtual .build-deps cargo curl gcc musl-dev rust
# install poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=$POETRY_VERSION python3 -
# install project dependencies
RUN poetry install --no-root --no-ansi $POETRY_ARGS && rm -rf $POETRY_CACHE_DIR


########################################################################################################################
# Application stage
# This stage is used to run the application

# python 3.13 is supported until Jun 30, 2029
# alpine 3.21 is supported until 1 Nov 2026
FROM python:3.13-alpine3.21

ARG TEST_FOLDER

ENV PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# need bash for running scripts
RUN apk add --no-cache bash

# add user and give ownership of app dir
RUN adduser -h /app -D vanotify

# From context and only what is necessary, importing relative to WORKDIR
COPY app/ app

# necessary files for mkdocs
COPY scripts/* /app/scripts/
COPY mkdocs.yml /app/mkdocs.yml

# Tests, using glob pattern to avoid copying
COPY $TEST_FOLDER/ tests

# Copy builder files - venv
COPY --from=builder /app/.venv /app/.venv

# these need to run only when POETRY_ARGS contain the proper setting
RUN if echo "$POETRY_ARGS" | grep -q "mkdocs"; then \
    poetry run python scripts/create_mkdoc_files.py \
    && poetry run mkdocs build;\
    fi;

# switch to user
USER vanotify

# CMD here for running when deployed to infra
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6012", "--workers", "4"]