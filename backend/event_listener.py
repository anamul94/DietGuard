import asyncio
import json
import aio_pika
import httpx
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FoodEventListener:
    def __init__(self, rabbitmq_url: str = "amqp://guest:guest@localhost:5672/", webhook_url: str = "http://localhost:8001/webhook"):
        self.rabbitmq_url = rabbitmq_url
        self.webhook_url = webhook_url

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                event_data = json.loads(message.body.decode())
                logger.info(f"Processing food event: {event_data.get('user_email')}")
                
                # Make POST request to webhook
                async with httpx.AsyncClient() as client:
                    response = await client.post(self.webhook_url, json=event_data)
                    logger.info(f"Webhook response: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def start_listening(self):
        connection = await aio_pika.connect_robust(self.rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue("food_events", durable=True)
        
        await queue.consume(self.process_message)
        logger.info("Started listening for food events...")
        
        try:
            await asyncio.Future()  # Run forever
        finally:
            await connection.close()

if __name__ == "__main__":
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8001/webhook")
    listener = FoodEventListener(rabbitmq_url, webhook_url)
    asyncio.run(listener.start_listening())