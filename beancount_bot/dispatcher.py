from typing import Union

from beancount.core.data import Transaction
from beancount.parser import parser

from beancount_bot.i18n import _


class Dispatcher:
    """
    Trading statement processor
    """

    def __init__(self) -> None:
        """
        The constructor of the processor will be built TransactionManager Performation.If started、/reload After the first statement analysis
        Constructor parameters pass **kwargs Incoming form
        """
        super().__init__()

    def quick_check(self, input_str: str) -> bool:
        """
        Quickly check if the input is compliant
        This method does not have to be accurately judged, but it does not recommend time consuming operation.
        :param input_str: User input
        :return: The user input can be processed by the processor
        """
        return True

    def process(self, input_str: str) -> Union[Transaction, str]:
        """
        Analysis input is transaction.If the input is not compliant, throw ValueError
        In general, it is not necessary to overload this method.
        :param input_str: User input
        :return: If resolved as a transaction，返回 Transaction；Otherwise it returns beancount Syntax string
        :raise NotMatchException: User input cannot be processed
        """
        tx_str = self._process_raw(input_str)
        try:
            tx = parser.parse_one(tx_str)
            if isinstance(tx, Transaction):
                return tx
            else:
                return tx_str
        except AssertionError:
            return tx_str

    def _process_raw(self, input_str: str) -> str:
        """
        Analysis input is beancount syntax
        Normal processor should be overloaded
        :param input_str:
        :return:
        """
        return '''
               2010-01-01 * "Payee" "Desc"
                 Assets:Unknown
                 Expenses:Unknown    + 1 CNY
               '''

    def get_name(self) -> str:
        """
        Get the processor name.In /help Display options
        :return: Processor name
        """
        return _("unknown")

    def get_usage(self) -> str:
        """
        Get help information.Used to display specific help content in /help, should be detailed
        :return:
        """
        return _("No help information.")
