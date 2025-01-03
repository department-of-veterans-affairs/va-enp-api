#! /bin/bash

POETRY_VERSION=$(grep "poetry_version" pyproject.toml | grep -m 1 -oE "[0-9]{1}.[0-9]{1,3}.[0-9]{1,3}")

if [[ -z $(head -1 poetry.lock | grep -E "${POETRY_VERSION}") ]]; then
  echo -E "Expected Poetry version: ${POETRY_VERSION}, found: $(head -1 poetry.lock | grep -oE "[0-9]{1}.[0-9]{1,3}.[0-9]{1,3}")"
  exit 1
fi

# Values set in pyroject.toml
pytest