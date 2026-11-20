FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY league.py results.py league.html drivers.json ./
ENV LEAGUE_DB=/data/league.sqlite3
RUN mkdir /data
EXPOSE 8080
CMD ["python","league.py"]
