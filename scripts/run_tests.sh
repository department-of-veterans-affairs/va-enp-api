#! /bin/bash

function display_result {
  RESULT=$1
  EXIT_STATUS=$2
  TEST=$3

  if [ $RESULT -ne 0 ]; then
    echo -e "\033[31m$TEST failed\033[0m"
    exit $EXIT_STATUS
  else
    echo -e "\033[32m$TEST passed\033[0m"
  fi
}


# Poetry version stability check
POETRY_VERSION=$(grep "poetry_version" pyproject.toml | grep -oE "[0-9]{1}.[0-9]{1,3}.[0-9]{1,3}")
head -1 poetry.lock | grep -qE "${POETRY_VERSION}"
display_result $? 1 "Expected Poetry version: ${POETRY_VERSION}, found: $(head -1 poetry.lock | grep -oE "[0-9]{1}.[0-9]{1,3}.[0-9]{1,3}")"


# Values set in pyroject.toml
# pytest