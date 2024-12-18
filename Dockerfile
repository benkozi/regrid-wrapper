FROM continuumio/miniconda3

RUN apt-get update --yes && apt-get install --yes tmux

COPY ./environment.yaml .
RUN conda env create --file environment.yaml
