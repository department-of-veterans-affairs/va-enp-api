#! /usr/bin/bash

APP_FOLDER='app'

# Wrap each check so it hides the output unless there is failure. Quotes needed in echo to preserve newline
args_check=$(flake8 --select=DCO020 $APP_FOLDER)
if [[ $? == '1' ]]; then
    echo "flake8 check failed"
    echo "$args_check"
    exit 1
fi

mypy_check=$(mypy $APP_FOLDER --strict)
if [[ $? == '1' ]]; then
    echo "mypy check failed"
    echo "$mypy_check"
    exit 1
fi

ruff_check=$(ruff check $APP_FOLDER)
if [[ $? == '1' ]]; then
    echo "ruff check failed"
    echo "$ruff_check"
    exit 1
fi

ruff_format=$(ruff format $APP_FOLDER)

echo -e "\nAll checks passed"
