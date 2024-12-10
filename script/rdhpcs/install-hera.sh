#!/usr/bin/env bash

set -e

cd /scratch2/NAGAPE/epic/Ben.Koziol
mkdir miniconda
cd miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod u+x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh -u -p ~/miniconda
./Miniconda3-latest-Linux-x86_64.sh -u -p /scratch2/NAGAPE/epic/Ben.Koziol/miniconda

export PATH=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/bin:$PATH