#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import openai
from openai import OpenAI
import os

import sys
import os
import configparser
import re
import psutil

from pathlib import Path
from prompt_file import PromptFile
from commands import get_command_result

MULTI_TURN = "off"
SHELL = ""

ENGINE = ''
TEMPERATURE = 0
MAX_TOKENS = 300

DEBUG_MODE = False

# api keys located in the same directory as this file
API_KEYS_LOCATION = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'openaiapirc')

PROMPT_CONTEXT = Path(__file__).with_name('current_context.txt')
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Read the secret_key from the ini file ~/.config/openaiapirc
# The format is:
# [openai]
# organization=<organization-id>
# secret_key=<your secret key>
# engine=<engine-name>
def create_template_ini_file():
    """
    If the ini file does not exist create it and add secret_key
    """
    if not os.path.isfile(API_KEYS_LOCATION):
        print('# Please create a file at {} and add your secret key'.format(API_KEYS_LOCATION))
        print('# The format is:\n')
        print('# [openai]')
        print('# organization_id=<organization-id>')
        print('# secret_key=<your secret key>\n')
        print('# engine=<engine-id>')
        sys.exit(1)

def initialize():
    """
    Initialize openAI and shell mode
    """
    global ENGINE
    global client

    # Check if file at API_KEYS_LOCATION exists
    create_template_ini_file()
    config = configparser.ConfigParser()
    config.read(API_KEYS_LOCATION)

    # TODO: The 'openai.organization' option isn't read in the client API. You will need to pass it when you instantiate the client, e.g. 'OpenAI(organization=config['openai']['organization_id'].strip('"').strip("'"))'
    # openai.organization = config['openai']['organization_id'].strip('"').strip("'")
    ENGINE = config['openai']['engine'].strip('"').strip("'")
    API_KEY = config['openai']['secret_key'].strip('"').strip("'")
    client = OpenAI(api_key=API_KEY)

    prompt_config = {
        'engine': ENGINE,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
        'shell': SHELL,
        'multi_turn': MULTI_TURN,
        'token_count': 0
    }

    return PromptFile(PROMPT_CONTEXT.name, prompt_config)

def get_query(prompt_file):
    """
    uses the stdin to get user input
    input is either treated as a command or as a Codex query

    Returns: command result or context + input from stdin
    """

    # get input from terminal or stdin
    if DEBUG_MODE:
        entry = input("prompt: ") + '\n'
    else:
        entry = sys.stdin.read()
    # first we check if the input is a command
    command_result, prompt_file = get_command_result(entry, prompt_file)

    # if input is not a command, then query Codex, otherwise exit command has been run successfully
    if command_result == "":
        return entry, prompt_file
    else:
        sys.exit(0)

def detect_shell():
    global SHELL
    global PROMPT_CONTEXT

    parent_process_name = psutil.Process(os.getppid()).name()
    POWERSHELL_MODE = bool(re.fullmatch('pwsh|pwsh.exe|powershell.exe', parent_process_name))
    BASH_MODE = bool(re.fullmatch('bash|bash.exe', parent_process_name))
    ZSH_MODE = bool(re.fullmatch('zsh|zsh.exe', parent_process_name))

    SHELL = "powershell" if POWERSHELL_MODE else "bash" if BASH_MODE else "zsh" if ZSH_MODE else "unknown"

    shell_prompt_file = Path(os.path.join(os.path.dirname(__file__), "..", "contexts", "{}-context.txt".format(SHELL)))

    if shell_prompt_file.is_file():
        PROMPT_CONTEXT = shell_prompt_file

if __name__ == '__main__':
    detect_shell()
    prompt_file = initialize()

    try:
        user_query, prompt_file = get_query(prompt_file)

        config = prompt_file.config if prompt_file else {
            'engine': ENGINE,
            'temperature': TEMPERATURE,
            'max_tokens': MAX_TOKENS,
            'shell': SHELL,
            'multi_turn': MULTI_TURN,
            'token_count': 0
        }

        # use query prefix to prime Codex for correct scripting language
        prefix = ""
        # prime codex for the corresponding shell type
        if config['shell'] == "zsh":
            prefix = '#!/bin/zsh\n\n'
        elif config['shell'] == "bash":
            prefix = '#!/bin/bash\n\n'
        elif config['shell'] == "powershell":
            prefix = '<# powershell #>\n\n'
        elif config['shell'] == "unknown":
            print("\n#\tUnsupported shell type, please use # set shell <shell>")
        else:
            prefix = '#' + config['shell'] + '\n\n'

        codex_query = prefix + prompt_file.read_prompt_file(user_query) + user_query

        # get the response from codex
        response = client.chat.completions.create(
            model=config['engine'],
            messages=[{"role":"user", "content":codex_query}],
            temperature=config['temperature'],
            max_tokens=config['max_tokens'],
            stop="#"
        )

        completion_all = response.choices[0].message.content

        print(completion_all)

        # append output to prompt context file
        if config['multi_turn'] == "on":
            if completion_all != "" or len(completion_all) > 0:
                prompt_file.add_input_output_pair(user_query, completion_all)

    except FileNotFoundError:
        print('\n\n# Codex CLI error: Prompt file not found, try again')
    except openai.RateLimitError as e:
        print('\n\n# Codex CLI error: Rate limit exceeded, try later')
        print(e)
    except openai.APIConnectionError:
        print('\n\n# Codex CLI error: API connection error, are you connected to the internet?')
    except openai.InvalidRequestError as e:
        print('\n\n# Codex CLI error: Invalid request - ' + str(e))
    except Exception as e:
        print('\n\n# Codex CLI error: Unexpected exception - ' + str(e))
