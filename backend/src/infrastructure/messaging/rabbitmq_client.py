import asyncio
import json
import aio_pika
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self, connection_url: str = "amqp://guest:guest@localhost:5672/"):
        self.connection_url = connection_url
        self.connection = None
        self.channel = None

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(self.connection_url)
            self.channel = await self.connection.channel()
            await self.channel.declare_queue("food_events", durable=True)
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    async def publish_food_event(self, event_data: Dict[Any, Any]):
        try:
            if not self.channel:
                await self.connect()
            
            message = aio_pika.Message(
                json.dumps(event_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message, routing_key="food_events"
            )
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    async def close(self):
        if self.connection:
            await self.connection.close()

# Global instance
rabbitmq_client = RabbitMQClient()