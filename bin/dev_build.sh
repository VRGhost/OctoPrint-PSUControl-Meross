#!/usr/bin/env bash

set -xe
THIS_DIR=$(readlink -f $(dirname "${BASH_SOURCE[0]}"))
PROJ_ROOT="${THIS_DIR}/.."

cd "${PROJ_ROOT}"
pytest
rm -f ./dist/*
bump2version --allow-dirty --no-commit --no-tag dev
python setup.py sdist