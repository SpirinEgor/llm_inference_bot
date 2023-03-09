from enum import Enum
from os import environ

from loguru import logger
from vk_api import VkApi, ApiError
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

from src.dialogue_tracker import DialogueTracker

_VK_API_TOKEN = "VK_API_TOKEN"
_VK_USERS_PREFIX = "vk_"


class Commands(Enum):
    help = "Помощь"
    reset = "Сбросить историю"
    role = "Установить роль"
    reset_role = "Сбросить роль на стандартную"


def handle_message(message: str, user_id: str, dialogue_tracker: DialogueTracker) -> str:
    if message.startswith("/"):
        command, *argument = message[1:].split(maxsplit=1)
        try:
            command = Commands[command]
        except KeyError:
            return "Неизвестная команда, попробуйте /help"

        if command == Commands.help:
            all_commands = [f" - /{it.name} -- {it.value}" for it in Commands]
            help_msg = (
                f"Максимальное число токенов/сообщений в истории: {dialogue_tracker.tokens_in_history}/{dialogue_tracker.messages_in_history}, "
                f"время жизни истории: {dialogue_tracker.max_alive_dialogue} секунд.\n"
                f"Текущая роль: {dialogue_tracker.get_role(user_id)}"
            )
            help_msg += "\nДоступные команды:\n" + "\n".join(all_commands)
            help_msg += "\nЕсли бот долго не отвечает, вероятно, OpenAI API перегружено, попробуйте позже."
            return help_msg
        elif command == Commands.reset:
            dialogue_tracker.reset_history(user_id)
            return "История диалога сброшена"
        elif command == Commands.role:
            if not argument:
                return "Необходимо указать роль: /role <role>"
            dialogue_tracker.set_role(user_id, argument[0])
            return "Роль установлена, история сброшена"
        elif command == Commands.reset_role:
            dialogue_tracker.reset_role(user_id)
            return "Роль сброшена на стандартную, история сброшена"

    return dialogue_tracker.on_message(message, user_id)


def main():
    logger.info(f"Starting VK bot")
    token = environ.get(_VK_API_TOKEN)
    vk_session = VkApi(token=token)
    vk_api = vk_session.get_api()
    vk_longpoll = VkLongPoll(vk_session)

    dialogue_tracker = DialogueTracker()

    logger.info("Start listening server")
    while True:
        try:
            for event in vk_longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
                    response = handle_message(event.text, _VK_USERS_PREFIX + str(event.user_id), dialogue_tracker)
                    vk_api.messages.send(user_id=event.user_id, message=response, random_id=get_random_id())
        except KeyboardInterrupt:
            logger.info(f"Keyboard interrupt received, stop listening server")
            exit()
        except ApiError:
            logger.info(f"Strange API error occurred, ignore it")
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    main()
