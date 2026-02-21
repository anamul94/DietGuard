.PHONY: build run stop clean dev install setup-db migrate

IMAGE_NAME = dietguard-backend
CONTAINER_NAME = dietguard-backend-app

build:
	docker build -t $(IMAGE_NAME) .

run:
	docker run -d --name $(CONTAINER_NAME) -p 8011:8000 --env-file .env $(IMAGE_NAME)

stop:
	docker stop $(CONTAINER_NAME) && docker rm $(CONTAINER_NAME)

clean:
	docker rmi $(IMAGE_NAME)

dev:
	uv run python main.py

install:
	uv sync

setup-db:
	uv run python setup_database.py

migrate:
	uv run alembic upgrade head