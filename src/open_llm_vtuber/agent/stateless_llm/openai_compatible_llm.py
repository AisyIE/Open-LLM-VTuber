"""Description: This file contains the implementation of the `AsyncLLM` class.
This class is responsible for handling asynchronous interaction with OpenAI API compatible
endpoints for language generation.
"""

from typing import AsyncIterator, List, Dict, Any
from openai import (
    AsyncStream,
    AsyncOpenAI,
    APIError,
    APIConnectionError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionChunk
from loguru import logger

from .stateless_llm_interface import StatelessLLMInterface


class AsyncLLM(StatelessLLMInterface):
    def __init__(
        self,
        model: str,
        base_url: str,
        llm_api_key: str = "z",
        organization_id: str = "z",
        project_id: str = "z",
        temperature: float = 1.0,
    ):
        """
        Initializes an instance of the `AsyncLLM` class.

        Parameters:
        - model (str): The model to be used for language generation.
        - base_url (str): The base URL for the OpenAI API.
        - organization_id (str, optional): The organization ID for the OpenAI API. Defaults to "z".
        - project_id (str, optional): The project ID for the OpenAI API. Defaults to "z".
        - llm_api_key (str, optional): The API key for the OpenAI API. Defaults to "z".
        - temperature (float, optional): What sampling temperature to use, between 0 and 2. Defaults to 1.0.
        """
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(
            base_url=base_url,
            organization=organization_id,
            project=project_id,
            api_key=llm_api_key,
        )

        logger.info(
            f"Initialized AsyncLLM with the parameters: {self.base_url}, {self.model}"
        )

    async def chat_completion(
        self, messages: List[Dict[str, Any]], system: str = None
    ) -> AsyncIterator[str]:
        """
        Generates a chat completion using the OpenAI API asynchronously.

        Parameters:
        - messages (List[Dict[str, Any]]): The list of messages to send to the API.
        - system (str, optional): System prompt to use for this completion.

        Yields:
        - str: The content of each chunk from the API response.

        Raises:
        - APIConnectionError: When the server cannot be reached
        - RateLimitError: When a 429 status code is received
        - APIError: For other API-related errors
        """
        logger.debug(f"Messages: {messages}")
        try:
            # If system prompt is provided, add it to the messages
            messages_with_system = messages
            if system:
                messages_with_system = [
                    {"role": "system", "content": system},
                    *messages,
                ]

            stream: AsyncStream[
                ChatCompletionChunk
            ] = await self.client.chat.completions.create(
                messages=messages_with_system,
                model=self.model,
                stream=True,
                temperature=self.temperature,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content is None:
                    chunk.choices[0].delta.content = ""
                yield chunk.choices[0].delta.content

        except APIConnectionError as e:
            logger.error(f"Failed to connect to the API: {e.__cause__}")
            raise

        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e.response}")
            raise

        except APIError as e:
            logger.error(f"LLM API: error occurred: {e}")
            logger.debug(f"Base URL: {self.base_url}")
            logger.debug(f"Model: {self.model}")
            logger.debug(f"Messages: {messages}")
            logger.debug(f"temperature: {self.temperature}")
            raise

        finally:
            # make sure the stream is properly closed
            # so when interrupted, no more tokens will being generated.
            logger.debug("Chat completion finished.")
            await stream.close()
            logger.debug("Stream closed.")
