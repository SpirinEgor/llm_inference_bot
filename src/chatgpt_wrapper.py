from dataclasses import dataclass, field
from enum import Enum
from os import getenv
from time import time

import openai
from loguru import logger


class MessageType(Enum):
    USER = "user"
    MODEL = "assistant"


@dataclass
class Dialogue:
    """Dataclass for storing dialogue history.
    History is a list of strings, where first string is the user input, second is the model response, etc.
    """

    user_id: str
    total_tokens: int = 0
    tokens: list[int] = field(default_factory=list)
    history: list[tuple[MessageType, str]] = field(default_factory=list)
    timestamp: float = field(default_factory=time)

    def clear(self):
        self.history.clear()
        self.tokens.clear()
        self.timestamp = time()
        self.total_tokens = 0

    def pop(self):
        self.history.pop(0)
        tokens_removed = self.tokens.pop(0)
        self.total_tokens -= tokens_removed

    def update(self, user_message: str, model_message: str, prompt_tokens: int, completion_tokens: int):
        self.history.append((MessageType.USER, user_message))
        self.history.append((MessageType.MODEL, model_message))

        self.tokens.append(prompt_tokens - self.total_tokens)
        self.tokens.append(completion_tokens)

        self.total_tokens = prompt_tokens + completion_tokens
        self.timestamp = time()


class ChatGPTWrapper:

    _OPENAI_API_KEY = "OPENAI_API_KEY"
    _MODEL_NAME = "gpt-3.5-turbo"
    DEFAULT_ROLE = "You are a helpful assistant that always response in russian language."

    def __init__(self, max_history_size: int = 4_000, max_alive_dialogue: float = 60 * 60, top_p: float = 0.9):
        logger.info(
            f"Initializing ChatGPT based on '{self._MODEL_NAME} model and nucleus sampling {top_p}. "
            f"Max tokens per history: {max_history_size}, seconds to clear history: {max_alive_dialogue}'"
        )
        openai.api_key = getenv(self._OPENAI_API_KEY)

        self._dialogue_history: dict[str, Dialogue] = {}
        self.max_history_size = max_history_size
        self.max_alive_dialogue = max_alive_dialogue

        self._custom_roles: dict[str, str] = {}

        self._top_p = top_p

    def on_message(self, user_message: str, user_id: str) -> str:
        if user_id not in self._dialogue_history:
            self._dialogue_history[user_id] = Dialogue(user_id)
        dialogue = self._dialogue_history[user_id]

        current_time = time()
        if current_time - dialogue.timestamp > self.max_alive_dialogue:
            dialogue.clear()

        while dialogue.total_tokens > self.max_history_size:
            dialogue.pop()

        role = self.get_role(user_id)
        messages = [{"role": "system", "content": role}]
        for message_type, message in dialogue.history:
            messages.append({"role": message_type.value, "content": message})
        messages.append({"role": MessageType.USER.value, "content": user_message})

        response = openai.ChatCompletion.create(model=self._MODEL_NAME, messages=messages, top_p=self._top_p)
        answer = response["choices"][0]["message"]["content"]
        prompt_tokens, completion_tokens = response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"]

        dialogue.update(user_message, answer, prompt_tokens, completion_tokens)
        logger.info(
            f"[User '{user_id}'] prompt: {prompt_tokens}, "
            f"completion: {completion_tokens}, total: {prompt_tokens + completion_tokens}"
        )

        return answer

    def reset_history(self, user_id: str):
        logger.info(f"Resetting history for user '{user_id}'")
        if user_id in self._dialogue_history:
            self._dialogue_history[user_id].clear()

    def set_role(self, user_id: str, role: str):
        logger.info(f"Setting role for user '{user_id}': '{role}'")
        self._custom_roles[user_id] = role

    def reset_role(self, user_id: str):
        logger.info(f"Resetting role for user '{user_id}'")
        if user_id in self._custom_roles:
            del self._custom_roles[user_id]

    def get_role(self, user_id: str) -> str:
        return self._custom_roles.get(user_id, self.DEFAULT_ROLE)
