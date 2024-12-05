FROM continuumio/miniconda3

COPY ./environment.yaml .
RUN conda env create --file environment.yaml
