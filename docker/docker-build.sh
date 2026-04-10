#!/usr/bin/env bash

set -eux

docker build \
  --platform linux/amd64 \
  -t deckyfre/regrid-wrapper-spack:0.0.7 \
  -t deckyfre/regrid-wrapper-spack:latest \
  -f Dockerfile-Spack \
  .

docker build \
  --platform linux/amd64 \
  -t deckyfre/regrid-wrapper-ci:0.0.5 \
  -t deckyfre/regrid-wrapper-ci:latest \
  -f Dockerfile-Spack-CI \
  .
