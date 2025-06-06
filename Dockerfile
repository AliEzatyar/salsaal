FROM python:3.10

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variable to tell pip where GDAL is
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal


WORKDIR /code

COPY requirements.txt /code/

RUN pip install --upgrade pip

ENV PIP_NO_CACHE_DIR=1

RUN pip install -r requirements.txt

COPY . /code/



