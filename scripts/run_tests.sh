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

# Pull in local variables for testing
source .env.local

# Parameters for pytest set in pyroject.toml
pytest
display_result $? 1 "unit tests"