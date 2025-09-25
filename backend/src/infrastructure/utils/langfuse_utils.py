import os
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Langfuse client
Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

# Get the configured client instance
langfuse_client = get_client()

# Initialize the Langfuse handler
langfuse_handler = CallbackHandler()

def get_langfuse_handler():
    """Get Langfuse callback handler for tracing"""
    return langfuse_handler

def flush_langfuse():
    """Flush events to Langfuse"""
    langfuse_client.flush()