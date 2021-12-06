'''vanparse.py'''

import os
import sys
import difflib

def indent(text, prefix, predicate=None):
    if predicate is None:
        def predicate(line):
            return line.strip()

    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if predicate(line) else line)
    return ''.join(prefixed_lines())

def out(text):
    import re
    import textwrap

    from shutil import get_terminal_size
    width = get_terminal_size().columns - 3

    indent_regex = re.compile(r'^(\s+)')
    wrapped_lines = []

    for line in text.split('\n'):
        exist_indent = re.search(indent_regex, line)
        pre_indent = exist_indent.groups()[0] if exist_indent else ''

        wrapped_lines.append(
            textwrap.fill(line, width=width, subsequent_indent=pre_indent)
        )

    print('\n'.join(wrapped_lines))

def print_option_help(args, option):
    text = ''
    if(option['action'] == 'grouping'):
        text += '  {}:\n'.format(option['names'][0])
    else:
        text += '  ' + ', '.join(option['names']) + '\n    ' + option['help'] + '\n\n'
        if(option['keywords'] != []):
            text += '    Arguments:\n    '
            for n, item in enumerate(option['keywords']):
                [[k, v]] = item.items()
                text += '{' + k
                text += '' if v == '' else '=' + str(v)
                text += '}' if n + 1 == len(option['keywords']) else '},'

        if(option['extra'] != ''):
            text += '{}\n\n'.format(indent(option['extra'], '    '))

    if(option['keywords'] != []):
        pass
    elif(option['action'] == 'default'):
        text += '    type: ' + option['type'].__name__
        text += '\n    default: {}\n'.format(option['default'])
        if(option['range'] is not None):
            text += '    range: ' +  option['range'] + '\n'

        if(option['choices'] is not None):
            text += '    choices: ' +  ', '.join(option['choices']) + '\n'
    elif(option['action'] == 'grouping'):
        for options in args:
            for op in options:
                if(op['group'] == option['names'][0]):
                    text += '  ' + ', '.join(op['names']) + ': ' + op['help'] + '\n'
    elif(option['action'] in ['store_true', 'store_false']):
        text += '    type: flag\n'
    else:
        text += '    type: unknown\n'

    if(option['group'] is not None):
        text += '    group: ' + option['group'] + '\n'
    out(text)

def print_program_help(root, the_args):
    text = ''
    for options in the_args:
        for option in options:
            if(not option['hidden']):
                if(option['action'] == 'grouping'):
                    text += "\n  {}:\n".format(option['names'][0])
                else:
                    text += '  ' + ', '.join(option['names']) + ': ' + option['help'] + '\n'
    text += '\n'
    if(root == 'auto-editor'):
        text += ('  Have an issue? Make an issue. Visit '
            'https://github.com/wyattblue/auto-editor/issues\n\n  The help option '
            'can also be used on a specific option:\n     auto-editor '
            '--frame_margin --help\n')
    out(text)

def get_option(item, the_args):
    for options in the_args:
        for option in options:
            dash = list(map(lambda n: n.replace('_', '-'), option['names']))
            if((item in option['names'] or item in dash)):
                return option
    return None

def _to_key(val):
    # (val: dict) -> str
    return val['names'][0].replace('-', '')

class ArgumentParser():
    def __init__(self, program_name, version, description=None):
        self.program_name = program_name
        self._version = version
        self.description = description

        self.args = []
        self.kwarg_defaults = {
            'nargs': 1,
            'type': str,
            'default': None,
            'action': 'default',
            'range': None,
            'choices': None,
            'group': None,
            'help': '',
            'keywords': [],
            'hidden': False,
            'extra': '',
        }

    def add_argument(self, *args, **kwargs):
        my_dict = {
            'names': list(args),
        }

        for key, item in self.kwarg_defaults.items():
            my_dict[key] = item

        for key, item in kwargs.items():
            if(key not in self.kwarg_defaults):
                raise ValueError('key {} not found.'.format(key))
            my_dict[key] = item

        self.args.append(my_dict)

    def parse_args(self, sys_args, log, root):
        if(sys_args == [] and self.description):
            out(self.description)
            sys.exit()

        if(sys_args == ['-v'] or sys_args == ['-V']):
            out('{} version {}'.format(self.program_name, self._version))
            sys.exit()

        return ParseOptions(sys_args, log, root, self.args)


"""
    Positional Arguments
        --rectangle 0,end,10,20,20,30,#000, ...

    Keyword Arguments
        --rectangle start=0,end=end,x1=10, ...

"""

class ParseOptions():

    def parse_parameters(self, val, op):

        # TODO: allow out-of-order arguments with keyword syntax.

        dic = {}
        keys = []
        for key in op['keywords']:
            [[k, v]] = key.items()
            keys.append(k)
            dic[k] = v

        for i, item in enumerate(val.split(',')):
            if(i+1 > len(keys)):
                print(f"Error! Too many arguments, starting with '{item}'", file=sys.stderr)
                sys.exit(1)

            dic[keys[i]] = item

        # Check if any positional args are not specified.
        for key, item in dic.items():
            if(item == ''):
                print(f"Error! parameter '{key}' is required.", file=sys.stderr)
                sys.exit(1)
        return dic

    def set_config(self, config_path, root):
        if(not os.path.isfile(config_path)):
            return

        with open(config_path, 'r') as file:
            lines = file.readlines()

        # Set attributes based on the config file to act as the new defaults.
        for item in lines:
            if('#' in item):
                item = item[: item.index('#')]
            item = item.replace(' ', '')
            if(item.strip() == '' or (not item.startswith(root))):
                continue
            value = item[item.index('=')+1 :]

            if(value[0] == "'" and value[-1] == "'"):
                value = value[1:-1]
            elif(value == 'None'):
                value = None
            elif('.' in value):
                value = float(value)
            else:
                value = int(value)

            key = item[: item.index('=')]
            key = key[key.rfind('.')+1:]

            if(getattr(self, key) != value):
                print('Setting {} to {}'.format(key, value), file=sys.stderr)
            setattr(self, key, value)

    def __init__(self, sys_args, log, root, *args):
        # Set the default options.
        option_names = []
        for options in args:
            for option in options:
                option_names.append(option['names'][0])
                key = _to_key(option)
                if(option['action'] == 'store_true'):
                    value = False
                elif(option['action'] == 'store_false'):
                    value = True
                elif(option['nargs'] != 1):
                    value = []
                else:
                    value = option['default']
                setattr(self, key, value)

        dirpath = os.path.dirname(os.path.realpath(__file__))
        self.set_config(os.path.join(dirpath, 'config.txt'), root)

        # Figure out command line options changed by user.
        my_list = []
        used_options = []
        _set = []
        setting_inputs = True
        option_list = 'input'
        list_type = str
        i = 0
        group = None
        while i < len(sys_args):
            item = sys_args[i]
            label = 'option' if item.startswith('--') else 'short'

            option = get_option(item, the_args=args)

            def error_message(args, item, label):

                def all_names(args):
                    name_set = set()
                    for options in args:
                        for opt in options:
                            for names in opt['names']:
                                name_set.add(names)
                    return name_set

                opt_list = all_names(args)
                close_matches = difflib.get_close_matches(item, opt_list)
                if(close_matches):
                    return 'Unknown {}: {}\n\n    Did you mean:\n        '.format(
                        label, item) + ', '.join(close_matches)
                return 'Unknown {}: {}'.format(label, item)

            if(option is None):
                # Unknown Option!
                if(setting_inputs and (option_list != 'input' or (option_list == 'input' and not item.startswith('-')))):
                    # Option is actually an input file, like example.mp4

                    if(option_list != 'input'):
                        _op = used_options[-1]
                        if(_op['keywords'] != []):
                            item = self.parse_parameters(item, _op)
                    my_list.append(item)
                else:
                    log.error(error_message(args, item, label))
            else:
                # We found the option.
                if(option_list is not None):
                    setattr(self, option_list, list(map(list_type, my_list)))

                setting_inputs = False
                option_list = None
                my_list = []

                if(option in used_options):
                    log.error('Cannot repeat option {} twice.'.format(option['names'][0]))

                used_options.append(option)

                key = _to_key(option)
                _set.append(key)

                if(option['action'] == 'grouping'):
                    group = key

                nextItem = None if i == len(sys_args) - 1 else sys_args[i+1]
                if(nextItem == '-h' or nextItem == '--help'):
                    print_option_help(args, option)
                    sys.exit()

                if(option['nargs'] != 1):
                    setting_inputs = True
                    option_list = key
                    list_type = option['type']
                elif(option['action'] == 'store_true'):
                    value = True
                elif(option['action'] == 'store_false'):
                    value = False
                else:
                    value = option['type'](nextItem)

                    if(option['choices'] is not None and value not in option['choices']):
                        option_name = option['names'][0]
                        my_choices = ', '.join(option['choices'])
                        log.error('{} is not a choice for {}\nchoices are:\n  {}'.format(
                            value, option_name, my_choices))
                    i += 1
                setattr(self, key, value)

            i += 1
        if(setting_inputs):
            setattr(self, option_list, list(map(list_type, my_list)))
        setattr(self, '_set', _set)
        if(self.help):
            print_program_help(root, args)
            sys.exit()
