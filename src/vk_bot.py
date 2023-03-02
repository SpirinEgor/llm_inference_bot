from os import environ

from loguru import logger
from vk_api import VkApi, ApiError
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

from src.chatgpt_wrapper import ChatGPTWrapper
from src.common import Commands

_VK_API_TOKEN = "VK_API_TOKEN"
_VK_USERS_PREFIX = "vk_"


def handle_message(message: str, user_id: str, chatgpt_wrapper: ChatGPTWrapper) -> str:
    if message.startswith("/"):
        command, *argument = message[1:].split(maxsplit=1)
        try:
            command = Commands[command]
        except KeyError:
            return "Неизвестная команда, попробуйте /help"

        if command == Commands.help:
            all_commands = [f" - /{it.name} -- {it.value}" for it in Commands]
            bot_setting = (
                f"Максимальное число токенов в истории: {chatgpt_wrapper.max_history_size} токенов, "
                f"время жизни истории: {chatgpt_wrapper.max_alive_dialogue} секунд.\n"
                f"Текущая роль: {chatgpt_wrapper.get_role(user_id)}"
            )
            return bot_setting + "\nДоступные команды:\n" + "\n".join(all_commands)
        elif command == Commands.reset:
            chatgpt_wrapper.reset_history(user_id)
            return "История диалога сброшена"
        elif command == Commands.role:
            if not argument:
                return "Необходимо указать роль: /role <role>"
            chatgpt_wrapper.set_role(user_id, argument[0])
            return "Роль установлена, рекомендую сбросить историю диалога: /reset"
        elif command == Commands.reset_role:
            chatgpt_wrapper.reset_role(user_id)
            return "Роль сброшена на стандартную"

    return chatgpt_wrapper.on_message(message, user_id)


def main():
    logger.info(f"Starting VK bot")
    token = environ.get(_VK_API_TOKEN)
    vk_session = VkApi(token=token)
    vk_api = vk_session.get_api()
    vk_longpoll = VkLongPoll(vk_session)

    chatgpt_wrapper = ChatGPTWrapper()

    logger.info("Start listening server")
    for event in vk_longpoll.listen():
        try:
            if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
                response = handle_message(event.text, _VK_USERS_PREFIX + str(event.user_id), chatgpt_wrapper)
                vk_api.messages.send(user_id=event.user_id, message=response, random_id=get_random_id())
        except KeyboardInterrupt:
            logger.info(f"Keyboard interrupt received, stop listening server")
            exit()
        except ApiError:
            logger.info(f"Strange API error occurred, ignore it")
        except TimeoutError:
            logger.info("Timeout error occurred, probably VK isn't available")
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    main()
