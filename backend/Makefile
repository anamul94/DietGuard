.PHONY: build run stop clean dev install

IMAGE_NAME = prodmeasure
CONTAINER_NAME = prodmeasure-app

build:
	docker build -t $(IMAGE_NAME) .

run:
	docker run -d --name $(CONTAINER_NAME) -p 8006:8000 --env-file .env $(IMAGE_NAME)

stop:
	docker stop $(CONTAINER_NAME) && docker rm $(CONTAINER_NAME)

clean:
	docker rmi $(IMAGE_NAME)

dev:
	uv run python main.py

install:
	uv sync