import traceback
import telebot
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity, Message, CallbackQuery

from beancount_bot import transaction
from beancount_bot.config import get_config, load_config
from beancount_bot.dispatcher import Dispatcher
from beancount_bot.i18n import _
from beancount_bot.session import get_session, SESS_AUTH, get_session_for, set_session
from beancount_bot.task import load_task, get_task
from beancount_bot.transaction import get_manager
from beancount_bot.util import logger

apihelper.ENABLE_MIDDLEWARE = True

bot = telebot.TeleBot(token=None, parse_mode=None)


@bot.middleware_handler(update_types=['message'])
def session_middleware(bot_instance, message):
    """
    Session middleware
    :param bot_instance:
    :param message:
    :return:
    """
    bot_instance.session = get_session_for(message.from_user.id)


#######
# Authentication #
#######

def check_auth() -> bool:
    """
    Check if you log in
    :return:
    """
    return SESS_AUTH in bot.session and bot.session[SESS_AUTH]


@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    """
    First chat time authentication
    :param message:
    :return:
    """
    auth = get_session(message.from_user.id, SESS_AUTH, False)
    if auth:
        bot.reply_to(message, _("Have been authenticated！"))
        return
    # 要求鉴权
    bot.reply_to(message, _("Welcome to the accounting robot!Please enter the authentication token:"))


def auth_token_handler(message: Message):
    """
    Login token callback
    :param message:
    :return:
    """
    if check_auth():
        return
    # Unconfirmation is considered an authentication token
    auth_token = get_config('bot.auth_token')
    if auth_token == message.text:
        set_session(message.from_user.id, SESS_AUTH, True)
        bot.reply_to(message, _("Authentic success！"))
    else:
        bot.reply_to(message, _("Authentication token error！"))


#######
# instruction #
#######


@bot.message_handler(commands=['reload'])
def reload_handler(message):
    """
    Overload configuration instruction
    :param message:
    :return:
    """
    if not check_auth():
        bot.reply_to(message, _("Please conduct authentication first！"))
        return
    load_config()
    load_task()
    bot.reply_to(message, _("Successful overload configuration！"))


@bot.message_handler(commands=['help'])
def help_handler(message):
    """
    Help instruction
    :param message:
    :return:
    """
    cmd = message.text
    dispatchers = get_manager().dispatchers
    if cmd == '/help':
        # Create a message button
        markup = InlineKeyboardMarkup()
        for ind, d in zip(range(len(dispatchers)), dispatchers):
            help_btn = _("help：{name}").format(name=d.get_name())
            markup.add(InlineKeyboardButton(help_btn, callback_data=f'help:{ind}'))
        # 帮助信息
        command_usage = [
            _("/start - Authentication"),
            _("/help - Using help"),
            _("/reload - Reload the configuration file"),
            _("/task - View, run the task"),
        ]
        help_text = \
            _("Account bill Bot\n\nAvailable instruction list：\n{command}\n\nTrade statement syntax help, select the corresponding module，Use /help [Module name] Check.").format(
                command='\n'.join(command_usage))
        bot.reply_to(message, help_text, reply_markup=markup)
    else:
        # Display detailed help
        name: str = cmd[6:]
        flag_found = False
        for d in dispatchers:
            if name.lower() == d.get_name().lower():
                show_usage_for(message, d)
                flag_found = True
        if not flag_found:
            bot.reply_to(message, _("The corresponding name of the transaction statement processor does not exist！"))


def show_usage_for(message: Message, d: Dispatcher):
    """
    Show the method of use of a specific processor
    :param message:
    :param d:
    :return:
    """
    usage = _("help：{name}\n\n{usage}").format(name=d.get_name(), usage=d.get_usage())
    bot.reply_to(message, usage)


@bot.callback_query_handler(func=lambda call: call.data[:4] == 'help')
def callback_help(call: CallbackQuery):
    """
    Help statement detailed help
    :param call:
    :return:
    """
    try:
        d_id = int(call.data[5:])
        dispatchers = get_manager().dispatchers
        show_usage_for(call.message, dispatchers[d_id])
    except Exception as e:
        logger.error(f'{call.id}：Unknown error！', e)
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, _("Unknown error！\n"+traceback.format_exc()))


@bot.message_handler(commands=['task'])
def task_handler(message):
    """
    Task instruction
    :param message:
    :return:
    """
    if not check_auth():
        bot.reply_to(message, _("Please conduct authentication first!"))
        return

    cmd = message.text
    tasks = get_task()
    if cmd == '/task':
        # Show all tasks
        all_tasks = ', '.join(tasks.keys())
        bot.reply_to(message,
                     _("Current registration task：{all_tasks}\n"
                       "able to pass /task [Task Name] Active trigger").format(all_tasks=all_tasks))
    else:
        # Run task
        dest = cmd[6:]
        if dest not in tasks:
            bot.reply_to(message, _("Task does not exist！"))
            return
        task = tasks[dest]
        task.trigger(bot)


#######
# trade #
#######


@bot.message_handler(func=lambda m: True)
def transaction_query_handler(message: Message):
    """
    Trading statement processing
    :param message:
    :return:
    """
    if not check_auth():
        auth_token_handler(message)
        return
    # Treated
    manager = get_manager()
    try:
        tx_uuid, tx = manager.create_from_str(message.text)
        # Create a message button
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(_("Revoke trading"), callback_data=f'withdraw:{tx_uuid}'))
        # 回复
        bot.reply_to(message, transaction.stringfy(tx), reply_markup=markup)
    except ValueError as e:
        logger.info(f'{message.from_user.id}：Unable to add transactions', e)
        bot.reply_to(message, e.args[0])
    except Exception as e:
        logger.error(f'{message.from_user.id}：An unknown mistake!Adding a transaction failed.', e)
        bot.reply_to(message, _("An unknown mistake!Adding a transaction failed.\n"+traceback.format_exc()))


@bot.callback_query_handler(func=lambda call: call.data[:8] == 'withdraw')
def callback_withdraw(call: CallbackQuery):
    """
    Transaction withdrawal callback
    :param call:
    :return:
    """
    auth = get_session(call.from_user.id, SESS_AUTH, False)
    if not auth:
        bot.answer_callback_query(call.id, _("Please conduct authentication first！"))
        return
    tx_uuid = call.data[9:]
    manager = get_manager()
    try:
        manager.remove(tx_uuid)
        # Modify the original message reply
        message = _("Transaction has been withdrawn")
        code_format = MessageEntity('code', 0, len(message))
        bot.edit_message_text(message,
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              entities=[code_format])
    except ValueError as e:
        logger.info(f'{call.id}：Unable to create trading', e)
        bot.answer_callback_query(call.id, e.args[0])
    except Exception as e:
        logger.error(f'{call.id}：An unknown mistake!Withdrawal of the transaction failed.', e)
        bot.answer_callback_query(call.id, _("An unknown mistake!Withdrawal of the transaction failed."))


def serving():
    """
    start up Bot
    :return:
    """

    # set up Token
    token = get_config('bot.token')
    bot.token = token
    # Set a proxy
    proxy = get_config('bot.proxy')
    if proxy is not None:
        apihelper.proxy = {'https': proxy}
    # start up
    bot.infinity_polling()
