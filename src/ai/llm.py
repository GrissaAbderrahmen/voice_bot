"""
OpenAI LLM client with streaming support.
Handles communication with GPT models.
"""

import os
from typing import Optional, AsyncGenerator, List, Dict, Any
from openai import OpenAI, AsyncOpenAI

from ..core.logger import get_logger
from ..core.config import Config

logger = get_logger("nova.ai.llm")


class LLMClient:
    """
    OpenAI GPT client with streaming responses.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
        temperature: float = 0.7
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: OpenAI API key (None = use env/config)
            model: Model to use
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-2)
        """
        # Get API key from multiple sources
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            config = Config()
            self.api_key = config.openai_api_key
        
        if not self.api_key:
            logger.error("OpenAI API key not found. Set OPENAI_API_KEY in .env")
            raise ValueError("OpenAI API key required")
        
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize clients
        self._client = OpenAI(api_key=self.api_key)
        self._async_client = AsyncOpenAI(api_key=self.api_key)
        
        logger.debug(f"LLM client initialized: model={model}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False
    ) -> str:
        """
        Send messages and get response.
        
        Args:
            messages: List of message dicts with "role" and "content"
            stream: Whether to stream response (use stream_chat for async)
        
        Returns:
            Assistant's response text
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False
            )
            
            reply = response.choices[0].message.content
            logger.debug(f"LLM response: {reply[:50]}...")
            return reply
            
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    async def chat_async(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        """Async version of chat()."""
        try:
            response = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            reply = response.choices[0].message.content
            logger.debug(f"LLM response: {reply[:50]}...")
            return reply
            
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    async def stream_chat(
        self,
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response token by token.
        
        Args:
            messages: List of message dicts
        
        Yields:
            Response text chunks
        """
        try:
            stream = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield f"Sorry, I encountered an error: {str(e)}"
    
    def stream_chat_sync(
        self,
        messages: List[Dict[str, str]]
    ):
        """
        Synchronous streaming (generator).
        
        Args:
            messages: List of message dicts
        
        Yields:
            Response text chunks
        """
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield f"Sorry, I encountered an error: {str(e)}"
    
    def simple_chat(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """
        Simple one-shot chat without conversation history.
        
        Args:
            user_message: User's message
            system_prompt: Optional system prompt
        
        Returns:
            Assistant's response
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_message})
        
        return self.chat(messages)
    
    @staticmethod
    def available_models() -> List[str]:
        """List commonly used models."""
        return [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
