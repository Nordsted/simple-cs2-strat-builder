FROM python:3.12-alpine
WORKDIR /app
COPY . .
RUN adduser -D -u 10001 appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
ENV PORT=8080 DATABASE_PATH=/app/data/strats.db
VOLUME ["/app/data"]
CMD ["python3", "app.py"]
