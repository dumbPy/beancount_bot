import copy
import datetime
import os
import time
import uuid
from typing import List, Tuple, Union

from beancount.core.data import Transaction
from beancount.parser import printer, parser

from beancount_bot.config import get_global, GLOBAL_MANAGER, get_config
from beancount_bot.dispatcher import Dispatcher
from beancount_bot.i18n import _
from beancount_bot.util import load_class

META_UUID = 'tgbot_uuid'
META_TIME = 'tgbot_time'

Uuid = str


class NotMatchException(Exception):
    pass


class TransactionManager:
    """
    Transaction information management
    """

    def __init__(self, dispatchers: List[Dispatcher], bean_file: str):
        self.dispatchers = dispatchers
        self.__bean_file = bean_file

    def create(self, tx: Union[Transaction, str]) -> Tuple[Uuid, Union[Transaction, str]]:
        """
        Create a transaction
        :param tx:
        :return:
        """
        tx_uuid = Uuid(uuid.uuid4())
        if isinstance(tx, str):
            # Save to the account
            with open(self.bean_file, 'a+', encoding='utf-8') as f:
                f.write(f"; TGBOT_START {tx_uuid}\n{tx}\n; TGBOT_END {tx_uuid}\n")
            return tx_uuid, tx
        elif isinstance(tx, Transaction):
            # Add control metadata
            tx = copy.deepcopy(tx)
            tx.meta[META_UUID] = tx_uuid
            tx.meta[META_TIME] = str(datetime.datetime.now())
            # Save to the account
            with open(self.bean_file, 'a+', encoding='utf-8') as f:
                printer.print_entry(tx, file=f)
            return tx_uuid, tx
        else:
            raise ValueError()

    def remove(self, tx_uuid: Uuid) -> Union[Transaction, str]:
        """
        Delete transaction
        :param tx_uuid:
        :return:
        """
        entries, errors, __ = parser.parse_file(self.bean_file)
        if len(errors) > 0:
            desc = '\n'.join(map(lambda err:
                                 _('Row {lineno}：{message}')
                                 .format(lineno=err.source["lineno"], message=err.message), errors))
            raise ValueError(_("Account file content error！\n{desc}").format(desc=desc))
        # 筛选交易
        to_delete = next(
            filter(lambda tx: tx.meta[META_UUID] == tx_uuid if META_UUID in tx.meta else False, entries),
            None
        )
        if to_delete is None:
            # 可能是非交易语句
            return self._remove_comment_wrapped(tx_uuid)
        # 统计删除行。避免删除其他语句。
        min_line = to_delete.meta['lineno']
        max_line = min_line
        for posting in to_delete.postings:
            max_line = max(max_line, posting.meta['lineno'])
        # 删除
        with open(self.bean_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(self.bean_file, 'w', encoding='utf-8') as f:
            f.write(''.join(lines[:min_line - 1] + lines[max_line:]))
        return to_delete

    def _remove_comment_wrapped(self, tx_uuid: Uuid) -> str:
        """
        Use a comment package
        :param tx_uuid:
        :return:
        """
        with open(self.bean_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 筛选列
        min_line = -1
        for i in range(len(lines)):
            if f'TGBOT_START {tx_uuid}' in lines[i]:
                min_line = i
                break
        max_line = -1
        for i in range(len(lines)):
            if f'TGBOT_END {tx_uuid}' in lines[i]:
                max_line = i
                break
        if min_line == -1 or max_line == -1:
            raise ValueError(_("Transaction does not exist！"))
        # 删除
        with open(self.bean_file, 'w', encoding='utf-8') as f:
            f.write(''.join(lines[:min_line] + lines[max_line + 1:]))
        return ''.join(lines[min_line + 1:max_line])[:-1]

    def create_from_str(self, tx_str) -> Union[Tuple[Uuid, Transaction], Tuple[None, str]]:
        """
        Create a transaction from a trading syntax
        :param tx_str:
        :return:
        """
        tx = self._parse_transaction(tx_str)
        tx_uuid, _ = self.create(tx)
        return tx_uuid, tx

    def _parse_transaction(self, tx_str) -> Transaction:
        for dispatcher in self.dispatchers:
            if not dispatcher.quick_check(tx_str):
                continue
            # Try to analyze
            try:
                tx = dispatcher.process(tx_str)
                return tx
            except NotMatchException:
                # Cannot be parsed by this parser
                continue
        else:
            # No match
            raise ValueError(_("Unable to identify this trading syntax"))

    @property
    def bean_file(self) -> str:
        params = {
            'year': time.strftime("%Y", time.localtime()),
            'month': time.strftime("%m", time.localtime()),
            'date': time.strftime("%d", time.localtime()),
        }
        bean_file = self.__bean_file
        for k, v in params.items():
            bean_file = bean_file.replace(f'{{{k}}}', v)
        # 创建父文件夹
        path = os.path.dirname(os.path.realpath(bean_file))
        os.makedirs(path, exist_ok=True)
        return bean_file


def stringfy(tx: Union[Transaction, str]) -> str:
    """
    Transaction is converted to a string
    :param tx:
    :return:
    """
    if isinstance(tx, str):
        return tx
    return printer.format_entry(tx)


def get_manager() -> TransactionManager:
    """
    Create management objects from configuration
    :return:
    """

    def create_manager():
        # Create a deliverer
        dispatchers = []
        for conf in get_config('transaction.message_dispatcher', []):
            clazz = load_class(conf['class'])
            dispatchers.append(clazz(**conf['args']))
        # get Bean File location
        bean_file: str = get_config('transaction.beancount_file')
        # Create an object
        return TransactionManager(dispatchers, bean_file)

    return get_global(GLOBAL_MANAGER, create_manager)
