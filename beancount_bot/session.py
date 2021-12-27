import json
import os.path
from types import MappingProxyType
from typing import Dict, Iterable

from beancount_bot.config import get_config
from beancount_bot.util import logger

SESS_AUTH = 'auth'

_session_cache: Dict[str, dict] = {}


def load_session():
    """
    Restore session data from file
    :return:
    """
    global _session_cache
    session_file = get_config('bot.session_file')
    if os.path.exists(session_file):
        with open(session_file, 'r', encoding='utf-8') as f:
            _session_cache = json.load(f)
        logger.debug("Restore session from file %s", _session_cache)


def get_session_for(uid: int) -> MappingProxyType:
    """
    Returns the non-variable view of the user session
    :param uid:
    :return:
    """
    uid = str(uid)
    if uid not in _session_cache:
        _session_cache[uid] = {}
    return MappingProxyType(_session_cache[uid])


def get_session(uid: int, key: str, default_value=None) -> object:
    """
    Returns a value for the user session
    :param uid:
    :param key:
    :param default_value:
    :return:
    """
    uid = str(uid)
    if uid not in _session_cache:
        _session_cache[uid] = {}
    if key not in _session_cache[uid]:
        return default_value
    return _session_cache[uid][key]


def set_session(uid: int, key: str, value: object):
    """
    Set user session value
    :param uid:
    :param key:
    :param value:
    :return:
    """
    uid = str(uid)
    if uid not in _session_cache:
        _session_cache[uid] = {}
    _session_cache[uid][key] = value
    # 保存缓存
    session_file = get_config('bot.session_file')
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(_session_cache, f)


def all_user(auth=True) -> Iterable[int]:
    """
    Get all users
    :param auth:
    :return:
    """
    if auth:
        return map(lambda t: int(t[0]), filter(lambda t: SESS_AUTH in t[1] and t[1][SESS_AUTH], _session_cache.items()))
    else:
        return map(int, _session_cache.keys())
