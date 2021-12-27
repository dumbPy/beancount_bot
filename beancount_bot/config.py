import yaml

from beancount_bot.i18n import _

global_object_map = {}

GLOBAL_CONFIG = 'config'
GLOBAL_MANAGER = 'manager'
GLOBAL_TASK = 'task'

config_file = ''


def set_global(key: str, obj):
    """
    Set global object
    :param key:
    :param obj:
    :return:
    """
    global global_object_map
    global_object_map[key] = obj


def get_global(key: str, default_producer: callable):
    """
    Get global objects
    :param key:
    :param default_producer:
    :return:
    """
    global global_object_map
    if key not in global_object_map:
        set_global(key, default_producer())
    return global_object_map[key]


def load_config(path=None):
    """
    From the file load configuration, clear the global object
    :param path:
    :return:
    """
    if path is None:
        path = config_file
    global global_object_map
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.full_load(f)
    global_object_map = {}
    set_global(GLOBAL_CONFIG, data)


def get_config_obj():
    """
    Get the configuration object
    :return:
    """

    def _exception():
        raise ValueError(_("Configure unloaded!"))

    return get_global(GLOBAL_CONFIG, _exception)


def get_config(key_path: str, default_value=None):
    """
    Get a configuration
    :param key_path:
    :param default_value:
    :return:
    """
    obj = get_config_obj()
    for ind in key_path.split('.'):
        if ind not in obj:
            return default_value
        obj = obj[ind]
    return obj
