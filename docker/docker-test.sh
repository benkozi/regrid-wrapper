#!/usr/bin/env bash

set -eux

docker run -v "$(readlink -f ..)":/opt/project \
  --rm deckyfre/regrid-wrapper-ci:latest \
  bash -c "export GITHUB_WORKSPACE=/opt/project &&
  pushd /opt/project &&
  bash .github/workflows/ci-setup.sh &&
  bash .github/workflows/ci-lint.sh &&
  bash .github/workflows/ci-test.sh"
