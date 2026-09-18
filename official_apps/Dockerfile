# 공식 앱 7개를 담은 이미지 하나.
# 컨테이너마다 command 로 어떤 앱을 띄울지 고릅니다.
#   docker compose 의 app-dev-projects, app-toolbox ... 를 보세요.
FROM python:3.11-slim
WORKDIR /srv
ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""
ENV PIP_INDEX_URL=${PIP_INDEX_URL} PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 DATA_DIR=/srv/data
CMD ["python", "-m", "dev_projects.server"]
