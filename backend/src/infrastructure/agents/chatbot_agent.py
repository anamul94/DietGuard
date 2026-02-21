import asyncio
import os
from typing import Annotated, TypedDict, Sequence
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langchain_community.tools.pubmed.tool import PubmedQueryRun
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from ..utils.redis_utils import RedisClient

import logging

logging.basicConfig(level=logging.INFO)


class ChatbotState(TypedDict):
    """State for the chatbot conversation"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_email: str


class MedicalChatbotAgent:
    """Medical chatbot agent with PubMed integration and medical report access"""
    
    def __init__(self):
        load_dotenv()
        
        # Initialize Redis client
        self.redis_client = RedisClient()
        
        # Initialize LLM
        self.llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=os.getenv("AWS_REGION"),
            temperature=0.3,
        )
        
        # Initialize tools
        self._pubmed_base = PubmedQueryRun()
        self.pubmed_tool = self._create_pubmed_tool()
        self.medical_report_tool = self._create_medical_report_tool()
        self.tools = [self.pubmed_tool, self.medical_report_tool]
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _create_medical_report_tool(self):
        """Create a tool to retrieve medical reports from Redis"""
        redis_client = self.redis_client
        
        @tool
        def get_medical_report(user_email: str) -> str:
            """Retrieve the user's medical report from the database.
            
            Use this tool when the user asks about their medical report, health conditions,
            or when you need medical history to provide personalized advice.
            
            Args:
                user_email: The user's email address
                
            Returns:
                The user's medical report if available, or a message indicating no report exists
            """
            try:
                medical_data = redis_client.get_report_data(user_email)
                if medical_data:
                    report = medical_data.get('data', {}).get('combined_response', '')
                    if report:
                        return f"Medical Report:\n{report}"
                return "No medical report found. Please ask the user to upload their medical report for personalized advice."
            except Exception as e:
                logging.error(f"Error retrieving medical report: {e}")
                return "Unable to retrieve medical report at this time."
        
        return get_medical_report

    def _create_pubmed_tool(self):
        """Create a wrapped PubMed tool with explicit logging"""
        base_tool = self._pubmed_base
        
        @tool
        def pubmed_search(query: str) -> str:
            """Search PubMed for medical and scientific literature.
            
            Use this tool to verify medical facts, find scientific evidence, 
            or cite research papers when providing nutritional advice.
            
            Args:
                query: The scientific or medical search query
            """
            logging.info(f"PubMed Search Invoked: '{query}'")
            try:
                result = base_tool.run(query)
                logging.info(f"PubMed Search success for: '{query}'")
                return result
            except Exception as e:
                logging.error(f"PubMed Search failed for '{query}': {e}")
                return f"Error searching PubMed: {e}"
        
        return pubmed_search
    
    def _get_system_message(self) -> str:
        """Get the system message for the chatbot"""
        return """You are Dr. Sarah Mitchell, a licensed clinical nutritionist and medical advisor.

**YOUR EXPERTISE:**
You specialize in:
- Medical topics and health conditions
- Nutrition and dietary advice  
- Healthy meal planning

**GUIDELINES:**
1. **Scope**: Focus on medical, nutrition, and healthy meal planning topics. For questions outside your expertise (e.g., weather, sports, politics), politely explain that you specialize in medical and nutrition topics and redirect the conversation.

2. **Tools Available**:
   - `get_medical_report`: Use this when users ask about their medical report or when you need their medical history for personalized advice.
   - `pubmed_search`: Use this to verify medical information and cite scientific sources from PubMed.

3. **SEARCH-FIRST MEDICAL ADVICE PROTOCOL**:
   - For ANY medical-related question, scientific inquiry, or nutritional advice request:
     1. **FIRST**, you MUST use the `pubmed_search` tool to look for latest scientific evidence or verification.
     2. **THEN**, provide your answer citing the findings from PubMed.
     3. Do NOT provide medical facts or advice based solely on your internal knowledge if it can be verified via PubMed.

4. **STRICT MEAL PLANNING PROTOCOL**:
   - Whenever a user asks for a meal plan (or any specific dietary recommendation):
     1. **FIRST**, you MUST use the `get_medical_report` tool to see if the user has uploaded their medical history.
     2. **IF** a report exists, use that data to create a highly personalized and clinically appropriate meal plan.
     3. **IF NO** report exists, you MUST NOT provide a detailed meal plan yet. Instead, politely ask the user to:
        - Upload their medical report for professional personalization, OR
        - Provide their details: **gender, age, and any existing medical conditions (like diabetes, hypertension, etc.)**.

5. **Communication Style**:
   - Be professional, concise, and evidence-based.
   - Use bullet points for clarity.
   - Cite PubMed sources when using scientific data.
   - Ask clarifying questions when needed.
   - Never mention that you're an AI - present yourself as a human nutritionist.

**IMPORTANT**: While maintaining professional medical guardrails, let the conversation feel natural. Polite redirects are better than canned rejections. Do not provide specific medical prescriptions or meal plans without individual context. Always prioritize PubMed evidence for medical questions."""
    
    def _should_continue(self, state: ChatbotState):
        """Determine if we should continue to tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are tool calls, continue to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        
        # Otherwise end
        return END
    
    def _call_model(self, state: ChatbotState):
        """Call the LLM with the current state"""
        messages = state["messages"]
        user_email = state["user_email"]
        
        # Add system message if not present
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            system_msg = SystemMessage(content=self._get_system_message())
            messages = [system_msg] + list(messages)
        
        # Add user email context for tools
        if user_email and not any("user_email:" in str(msg.content) for msg in messages if isinstance(msg, SystemMessage)):
            email_context = SystemMessage(
                content=f"**USER EMAIL**: {user_email}\n\nWhen using the get_medical_report tool, pass this email address."
            )
            messages = [messages[0], email_context] + list(messages[1:])
        
        try:
            response = self.llm_with_tools.invoke(messages)
            return {"messages": [response]}
        except Exception as e:
            logging.error(f"Error calling model: {e}")
            error_msg = AIMessage(
                content="I apologize, but I'm experiencing technical difficulties. Please try again in a moment."
            )
            return {"messages": [error_msg]}
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(ChatbotState)
        
        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                END: END
            }
        )
        
        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    async def chat(self, user_email: str, message: str) -> dict:
        """
        Process a chat message from a user
        
        Args:
            user_email: User's email address
            message: User's message
            
        Returns:
            dict with 'response' and 'sources'
        """
        try:
            # Get or create chat session
            session_data = self.redis_client.get_chat_session(user_email)
            
            messages = []
            if session_data:
                # Load existing conversation with validation
                messages_data = session_data.get("data", {}).get("messages", [])
                for msg_data in messages_data:
                    try:
                        # Only load simple human and AI messages (skip corrupted tool messages)
                        if isinstance(msg_data, dict) and "type" in msg_data and "content" in msg_data:
                            if msg_data["type"] == "human" and isinstance(msg_data["content"], str):
                                messages.append(HumanMessage(content=msg_data["content"]))
                            elif msg_data["type"] == "ai" and isinstance(msg_data["content"], str):
                                messages.append(AIMessage(content=msg_data["content"]))
                    except Exception as e:
                        logging.warning(f"Skipping invalid message in history: {e}")
                        continue
            
            # Add new user message
            messages.append(HumanMessage(content=message))
            
            # Create initial state
            initial_state = {
                "messages": messages,
                "user_email": user_email
            }
            
            # Run the graph
            result = await asyncio.to_thread(
                self.graph.invoke,
                initial_state
            )
            
            # Extract response
            final_messages = result["messages"]
            
            # Find the last AI message (final response)
            ai_response = None
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage) and not hasattr(msg, 'tool_calls') or (hasattr(msg, 'tool_calls') and not msg.tool_calls):
                    ai_response = msg.content
                    break
            
            if not ai_response:
                ai_response = final_messages[-1].content if final_messages else "No response generated"
            
            # Save only human and final AI messages to Redis (exclude tool messages)
            messages_to_save = []
            for msg in final_messages:
                if isinstance(msg, HumanMessage):
                    messages_to_save.append({"type": "human", "content": msg.content})
                elif isinstance(msg, AIMessage) and msg.content and (not hasattr(msg, 'tool_calls') or not msg.tool_calls):
                    # Only save AI messages that have content and are not tool calls
                    messages_to_save.append({"type": "ai", "content": msg.content})
            
            self.redis_client.save_chat_session(user_email, {"messages": messages_to_save})
            
            # Extract sources if PubMed was used
            sources = []
            # Note: PubMed tool results would be in the tool messages
            # We can extract them if needed
            
            return {
                "response": ai_response,
                "sources": sources
            }
            
        except Exception as e:
            logging.error(f"Error in chat: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your message. Please try again.",
                "sources": []
            }
    
    async def get_chat_history(self, user_email: str) -> dict:
        """Get chat history for a user"""
        try:
            session_data = self.redis_client.get_chat_session(user_email)
            
            if not session_data:
                return {"messages": [], "last_updated": None}
            
            # Validate and clean messages
            messages = []
            for msg in session_data.get("data", {}).get("messages", []):
                if isinstance(msg, dict) and "type" in msg and "content" in msg and isinstance(msg["content"], str):
                    messages.append(msg)
            
            return {
                "messages": messages,
                "last_updated": session_data.get("timestamp")
            }
        except Exception as e:
            logging.error(f"Error getting chat history: {e}")
            return {"messages": [], "last_updated": None}
    
    async def clear_chat_history(self, user_email: str) -> bool:
        """Clear chat history for a user"""
        return self.redis_client.delete_chat_session(user_email)


# Create singleton instance
chatbot_agent = MedicalChatbotAgent()
