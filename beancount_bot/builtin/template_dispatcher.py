import datetime
import itertools
from typing import List, Mapping

import yaml

from beancount_bot import logger
from beancount_bot.dispatcher import Dispatcher
from beancount_bot.transaction import NotMatchException

_CH_CLASS = [' ', '\"', '\\', '>']
_STATE_MAT = [
    # 空, ", \, >, 其他字符
    [0, 2, -1, 4, 1],  # 0: 空格
    [0, 2, -1, 4, 1],  # 1: 词
    [2, 0, 3, 2, 2],  # 2: 字符串
    [2, 2, 2, 2, 2],  # 3: 转义
    [0, 2, -1, -1, 1],  # 4: 符号
]


def split_command(cmd):
    """
    切分输入指令。按照空格分割，允许使用双引号字符串、反斜杠转义
    :param cmd:
    :return:
    """
    state = 0
    words: List[str] = []

    for i in range(len(cmd)):
        ch = cmd[i]
        # 字符类
        if ch in _CH_CLASS:
            ch_class = _CH_CLASS.index(ch)
        else:
            ch_class = 4
        # 状态转移
        state, old_state = _STATE_MAT[state][ch_class], state
        if state == -1:
            raise ValueError(f"位置 {i}：语法错误！不应出现符号 {ch}。")
        # 进入事件
        if state != old_state and old_state != 3:
            if state in [1, 2, 4]:
                words.append('')
            if state in [2, 3]:
                continue
        # 状态事件
        if state != 0:
            words[-1] += ch
    if state not in [0, 1, 4]:
        raise ValueError(f"位置 {len(cmd)}：语法错误！字符串、转义未结束。")
    return words


def _to_list(el):
    if isinstance(el, list):
        return el
    return [el]


Template = Mapping


def print_one_usage(template: Template) -> str:
    """
    打印一个模板的语法提示
    :param template:
    :return:
    """
    usage = ''
    # 指令
    command = template['command']
    if isinstance(command, list):
        usage += '|'.join(command)
    else:
        usage += command
    # 参数
    if 'args' in template:
        usage += ' ' + ' '.join(template['args'])
    # 可选参数
    if 'optional_args' in template:
        usage += ' ' + ' '.join(map(lambda s: f'[{s}]', template['optional_args']))
    return usage


class TemplateDispatcher(Dispatcher):
    """
    模板处理器。通过 Json 模板生成交易信息。
    """

    def __init__(self, template_config: str):
        with open(template_config, 'r', encoding='utf-8') as f:
            data = yaml.load(f)
        self.config = data['config']
        self.templates = data['templates']

    def quick_check(self, input_str: str) -> bool:
        words = split_command(input_str)
        prefixes = map(lambda t: _to_list(t['command']), self.templates)
        prefixes = itertools.chain(*prefixes)
        # 开头相同且有空格隔开
        return any(map(lambda prefix: words[0] == prefix, prefixes))

    def _process_raw(self, input_str: str) -> str:
        words = split_command(input_str)
        cmd, args = words[0], words[1:]
        # 选择模板
        template = next(
            filter(lambda t: cmd in _to_list(t['command']), self.templates),
            None
        )
        if template is None:
            raise NotMatchException()
        # 默认参数
        arg_map = {
            'account': self.config['default_account'],
            'date': datetime.date.today().isoformat(),
            'command': cmd,
        }
        # 解析目标账户（>语法）
        if '>' in args:
            split_at = args.index('>')
            args, account = args[:split_at], args[split_at + 1:]
            if len(account) != 1:
                raise ValueError("语法错误！不支持多目标账户。")
            arg_map['account'] = self.config['accounts'][account[0]]
        # 参数获取
        if 'args' in template:
            args_need = template['args']
            if len(args) < len(args_need):
                raise ValueError('参数过少！语法：' + print_one_usage(template))
            arg_map.update({k: v for k, v in zip(args_need, args)})
            args = args[len(args_need):]
        if 'optional_args' in template:
            optional_args = template['optional_args']
            if len(args) > len(optional_args):
                raise ValueError('参数过多！语法：' + print_one_usage(template))
            arg_map.update({k: v for k, v in zip(optional_args, args)})
            for empty_k in optional_args[len(args):]:
                arg_map[empty_k] = ''
            args = args[len(optional_args):]
        if len(args) != 0:
            raise ValueError('参数过多！语法：' + print_one_usage(template))
        # 计算待计算参数
        if 'computed' in template:
            for k, expr in template['computed'].items():
                arg_map[k] = eval(expr, None, arg_map)
        # 进行模板替换
        logger.debug('模板参数 %s', arg_map)
        ret = template['template']
        for k, v in arg_map.items():
            ret = ret.replace(f'{{{k}}}', str(v))
        return ret