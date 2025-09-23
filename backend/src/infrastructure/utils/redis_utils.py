import redis
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)

class RedisClient:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD'),
            decode_responses=True
        )
    
    def _generate_key(self, user_id: str, data_type: str) -> str:
        """Generate Redis key with pattern: dietguard:{data_type}:{user_id}"""
        return f"dietguard:{data_type}:{user_id}"
    
    def save_report_data(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Save report data with 12 hours expiration"""
        try:
            key = self._generate_key(user_id, "report")
            data_with_timestamp = {
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=12)).isoformat()
            }
            # Set with 12 hours expiration (43200 seconds)
            result = self.redis_client.setex(key, 43200, json.dumps(data_with_timestamp))
            logging.info(f"Redis save result for key {key}: {result}")
            return result
        except Exception as e:
            logging.error(f"Redis save failed for key {key}: {e}")
            return False
    
    def get_report_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get report data if not expired"""
        try:
            key = self._generate_key(user_id, "report")
            data = self.redis_client.get(key)
            logging.info(f"Redis get result for key {key}: {'Found' if data else 'Not found'}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logging.error(f"Redis get failed for key {key}: {e}")
            return None
    
    def delete_report_data(self, user_id: str) -> bool:
        """Delete report data for user"""
        try:
            key = self._generate_key(user_id, "report")
            result = self.redis_client.delete(key)
            logging.info(f"Redis delete result for key {key}: {result}")
            return bool(result)
        except Exception as e:
            logging.error(f"Redis delete failed for key {key}: {e}")
            return False
    
    def get_nutrition_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get nutrition data if not expired"""
        try:
            key = self._generate_key(user_id, "nutrition")
            data = self.redis_client.get(key)
            logging.info(f"Redis get nutrition result for key {key}: {'Found' if data else 'Not found'}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logging.error(f"Redis get nutrition failed for key {key}: {e}")
            return None
    
    def save_nutrition_data(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Save nutrition data with 24 hours expiration"""
        try:
            key = self._generate_key(user_id, "nutrition")
            data_with_timestamp = {
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            # Set with 24 hours expiration (86400 seconds)
            result = self.redis_client.setex(key, 86400, json.dumps(data_with_timestamp))
            logging.info(f"Redis save nutrition result for key {key}: {result}")
            return result
        except Exception as e:
            logging.error(f"Redis save nutrition failed for key {key}: {e}")
            return False