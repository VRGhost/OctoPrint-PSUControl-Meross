#!/usr/bin/env bash

set -xe
THIS_DIR=$(readlink -f $(dirname "${BASH_SOURCE[0]}"))
PROJ_ROOT="${THIS_DIR}/.."

#bump2version -h
#bump2version --list
#exit 1
cd "${PROJ_ROOT}"
bump2version --verbose --allow-dirty --no-commit --no-tag dev