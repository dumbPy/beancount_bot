import click

from beancount_bot import bot, config as conf, __VERSION__
from beancount_bot.config import load_config, get_config
from beancount_bot.i18n import _
from beancount_bot.session import load_session
from beancount_bot.task import load_task, start_schedule_thread
from beancount_bot.transaction import get_manager
from beancount_bot.util import logger


@click.command()
@click.version_option(__VERSION__, '-V', '--version', help=_("Display version information"))
@click.help_option(help=_("Display help information"))
@click.option('-c', '--config', default='beancount_bot.yml', help=_("Profile path"))
def main(config):
    """
    Telegram robot for Beancount
    """
    logger.setLevel('INFO')
    # Load configuration
    logger.info("Load configuration：%s", config)
    conf.config_file = config
    load_config()
    # Set log level
    logger.setLevel(get_config('log.level', 'INFO'))
    # Load session
    logger.info("Load session...")
    load_session()
    # Create a management object
    logger.info("Create a management object...")
    get_manager()
    # Load timing task
    logger.info("Load timing task...")
    load_task()
    start_schedule_thread()
    # start up
    logger.info("start up Bot...")
    bot.serving()


if __name__ == '__main__':
    main()
