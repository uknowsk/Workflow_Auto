# PC 설치형 앱은 보통 그 PC에서 직접 실행합니다(python server.py).
# 서버에 올릴 때만 이 Dockerfile 을 쓰세요.
FROM python:3.11-slim
WORKDIR /srv
ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""
ENV PIP_INDEX_URL=${PIP_INDEX_URL} PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 9002
CMD ["python", "server.py"]
