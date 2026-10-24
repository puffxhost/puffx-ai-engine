FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 puffx && mkdir -p /data && chown -R puffx:puffx /app /data
USER puffx
EXPOSE 8000
CMD ["uvicorn","api.app:app","--host","0.0.0.0","--port","8000"]
