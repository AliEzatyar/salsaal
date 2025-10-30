FROM python:3.10

ARG C_FORCE_ROOT=false

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV C_FORCE_ROOT=${C_FORCE_ROOT}

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

# Create non-root user
RUN groupadd -r celery && useradd -r -g celery celery

WORKDIR /code

COPY requirements.txt /code/

RUN pip install --upgrade pip

ENV PIP_NO_CACHE_DIR=1

RUN pip install -r requirements.txt

COPY . /code/

# Change ownership to non-root user
RUN chown -R celery:celery /code

# Switch to non-root user
USER celery

# Set the working directory to project root
WORKDIR /code/project

CMD ["celery", "-A", "celery", "worker", "--loglevel=info"]