FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /tmp/lab-requirements.txt
RUN pip install --no-cache-dir -r /tmp/lab-requirements.txt
CMD ["sleep", "infinity"]
