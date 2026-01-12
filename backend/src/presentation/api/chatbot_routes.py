from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from ...infrastructure.agents.chatbot_agent import chatbot_agent
import logging

logging.basicConfig(level=logging.INFO)

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    email: EmailStr
    message: str


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    sources: List[str] = []


class ChatMessage(BaseModel):
    """Chat message model"""
    type: str  # 'human' or 'ai'
    content: str


class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    messages: List[ChatMessage]
    last_updated: Optional[str] = None


class DeleteResponse(BaseModel):
    """Response model for delete operations"""
    message: str


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest):
    """
    Send a message to the medical chatbot
    
    - **email**: User's email address (used for session management)
    - **message**: User's question or message
    
    Returns the chatbot's response and any PubMed sources used
    """
    try:
        logging.info(f"Chat request from {request.email}: {request.message[:50]}...")
        
        result = await chatbot_agent.chat(request.email, request.message)
        
        return ChatResponse(
            response=result["response"],
            sources=result["sources"]
        )
        
    except Exception as e:
        logging.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your message. Please try again."
        )


@router.get("/chat/history/{email}", response_model=ChatHistoryResponse)
async def get_chat_history(email: EmailStr):
    """
    Get chat history for a user
    
    - **email**: User's email address
    
    Returns the conversation history and last update timestamp
    """
    try:
        logging.info(f"Fetching chat history for {email}")
        
        history = await chatbot_agent.get_chat_history(email)
        
        messages = [
            ChatMessage(type=msg["type"], content=msg["content"])
            for msg in history["messages"]
        ]
        
        return ChatHistoryResponse(
            messages=messages,
            last_updated=history["last_updated"]
        )
        
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching chat history."
        )


@router.delete("/chat/history/{email}", response_model=DeleteResponse)
async def clear_chat_history(email: EmailStr):
    """
    Clear chat history for a user
    
    - **email**: User's email address
    
    Deletes all conversation history for the specified user
    """
    try:
        logging.info(f"Clearing chat history for {email}")
        
        success = await chatbot_agent.clear_chat_history(email)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="No chat history found for this user."
            )
        
        return DeleteResponse(
            message=f"Chat history cleared for {email}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while clearing chat history."
        )
