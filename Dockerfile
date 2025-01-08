FROM continuumio/miniconda3

RUN apt-get update --yes && apt-get install --yes tmux vim less

COPY ./environment.yaml .
RUN conda env create --file environment.yaml
