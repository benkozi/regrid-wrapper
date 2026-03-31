#!/usr/bin/env bash

set -eux

docker build \
  --platform linux/amd64 \
  -t deckyfre/regrid-wrapper-spack:0.0.6 \
  -t deckyfre/regrid-wrapper-spack:latest \
  -f Dockerfile-Spack \
  .

docker build \
  --platform linux/amd64 \
  -t deckyfre/regrid-wrapper-ci:0.0.4 \
  -t deckyfre/regrid-wrapper-ci:latest \
  -f Dockerfile-Spack-CI \
  .
