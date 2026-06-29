FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

ENTRYPOINT ["python"]
CMD ["monitor.py"]
