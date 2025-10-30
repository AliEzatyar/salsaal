FROM python:3.10

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -r fastapi && useradd -r -g fastapi fastapi

WORKDIR /code

COPY requirements.txt /code/

RUN pip install --upgrade pip

ENV PIP_NO_CACHE_DIR=1

RUN pip install -r requirements.txt

COPY . /code/

# Change ownership to non-root user
RUN chown -R fastapi:fastapi /code

# Switch to non-root user
USER fastapi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
