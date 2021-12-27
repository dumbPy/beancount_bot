import datetime
import itertools
from typing import List, Mapping

import yaml

from beancount_bot.dispatcher import Dispatcher
from beancount_bot.i18n import _
from beancount_bot.transaction import NotMatchException
from beancount_bot.util import logger

_CH_CLASS = [' ', '\"', '\\', '<']
_STATE_MAT = [
    # Empty, ", \, <, other characters
    [0, 2, -1, 4, 1],  # 0: Space
    [0, 2, -1, 4, 1],  # 1: word
    [2, 0, 3, 2, 2],  # 2: String
    [2, 2, 2, 2, 2],  # 3: Escape
    [0, 2, -1, -1, 1],  # 4: symbol
]


def split_command(cmd):
    """
    Separate input instructions.Split by space, allowing double quotation strings, backlaps
    :param cmd:
    :return:
    """
    state = 0
    words: List[str] = []

    for i in range(len(cmd)):
        ch = cmd[i]
        # Character class
        if ch in _CH_CLASS:
            ch_class = _CH_CLASS.index(ch)
        else:
            ch_class = 4
        # State transfer
        state, old_state = _STATE_MAT[state][ch_class], state
        if state == -1:
            raise ValueError(_("Location {pos}：Grammatical errors!Should not appear {ch}.").format(pos=i, ch=ch))
        # 进入事件
        if state != old_state and old_state != 3:
            if state in [1, 2, 4]:
                words.append('')
            if state in [2, 3]:
                continue
        # Status event
        if state != 0:
            words[-1] += ch
    if state not in [0, 1, 4]:
        raise ValueError(_("Location {pos}：Grammatical errors!String, the escape is not over.").format(pos=len(cmd)))
    return words


def _to_list(el):
    if isinstance(el, list):
        return el
    return [el]


Template = Mapping


def print_one_usage(template: Template) -> str:
    """
    Print a template syntax prompt
    :param template:
    :return:
    """
    usage = ''
    # 指令
    command = template['command']
    if isinstance(command, list):
        usage += '(' + '|'.join(command) + ')'
    else:
        usage += command
    # parameter
    if 'args' in template:
        usage += ' ' + ' '.join(template['args'])
    # Optional parameters
    if 'optional_args' in template:
        usage += ' ' + ' '.join(map(lambda s: f'[{s}]', template['optional_args']))
    return usage


class TemplateDispatcher(Dispatcher):
    """
    Template processor.Based on the JSON template to generate transaction information.
    """

    def get_name(self) -> str:
        return _("template")

    def get_usage(self) -> str:
        if len(self.templates) > 0:
            command_usage = '\n'.join([f'  - {print_one_usage(t)}' for t in self.templates])
        else:
            command_usage = _("No template is defined")

        default_account = self.config['default_account']

        if len(self.config['accounts']) > 0:
            account_alias = '\n'.join([f'  {k} - {v}' for k, v in self.config['accounts'].items()])
        else:
            account_alias = _("No account")

        return _('Template instruction format: instruction name required [Optional parameters] <Target account\n'
                 '  1. Directive names can have multiple, record "(instruction name 1 |2|...)“；\n'
                 '  2. Target accounts can be omitted.The default account will be omitted\n\n'
                 'Currently defined template：\n{command_usage}\n\n'
                 'Default account：{default_account}\nSupported account：\n{account_alias}') \
            .format(command_usage=command_usage, default_account=default_account, account_alias=account_alias)

    def __init__(self, template_config: str):
        """
        :param template_config: Template configuration file path.Specific grammar template.example.yml
        """
        super().__init__()
        with open(template_config, 'r', encoding='utf-8') as f:
            data = yaml.full_load(f)
        self.config = data['config']
        self.templates = data['templates']

    def quick_check(self, input_str: str) -> bool:
        words = split_command(input_str)
        prefixes = map(lambda t: _to_list(t['command']), self.templates)
        prefixes = itertools.chain(*prefixes)
        # The same is the same and spaced apart
        return any(map(lambda prefix: words[0] == prefix, prefixes))

    def _process_raw(self, input_str: str) -> str:
        words = split_command(input_str)
        cmd, args = words[0], words[1:]
        # Select template
        template = next(
            filter(lambda t: cmd in _to_list(t['command']), self.templates),
            None
        )
        if template is None:
            raise NotMatchException()
        # Default parameters
        arg_map = {
            'account': self.config['default_account'],
            'date': datetime.date.today().isoformat(),
            'command': cmd,
        }
        # Analysis of target accounts (<syntax)
        if '<' in args:
            split_at = args.index('<')
            args, account = args[:split_at], args[split_at + 1:]
            if len(account) != 1:
                raise ValueError(_("Grammatical errors!Multi-objective accounts are not supported."))
            arg_map['account'] = self.config['accounts'][account[0]]
        # Parameter acquisition
        if 'args' in template:
            args_need = template['args']
            if len(args) < len(args_need):
                raise ValueError(_("Too few parameters!grammar：{syntax}").format(syntax=print_one_usage(template)))
            arg_map.update({k: v for k, v in zip(args_need, args)})
            args = args[len(args_need):]
        if 'optional_args' in template:
            optional_args = template['optional_args']
            if len(args) > len(optional_args):
                raise ValueError(_("Excessive parameters!grammar：{syntax}").format(syntax=print_one_usage(template)))
            arg_map.update({k: v for k, v in zip(optional_args, args)})
            for empty_k in optional_args[len(args):]:
                arg_map[empty_k] = ''
            args = args[len(optional_args):]
        if len(args) != 0:
            raise ValueError(_("Excessive parameters!grammar：{syntax}").format(syntax=print_one_usage(template)))
        # Calculate parameters to be calculated
        if 'computed' in template:
            for k, expr in template['computed'].items():
                arg_map[k] = eval(expr, None, arg_map)
        # Template replacement
        logger.debug('Template parameters %s', arg_map)
        ret = template['template']
        for k, v in arg_map.items():
            ret = ret.replace(f'{{{k}}}', str(v))
        return ret
