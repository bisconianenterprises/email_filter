import os
import poplib
import sys
import terminal
import json
import re
import math
from email import message_from_bytes
from email.header import decode_header, make_header
from typing import List

# prints the supplied fields in an aligned table
def columns_print(cols: List[str], headers: List[dict]):
    if len(headers) > 0:
        print()
        column_print(cols, headers[0], True)
        for header in headers:
            column_print(cols, header)

# prints the supplied fields in a single aligned row
def column_print(cols: List[str], header: dict, header_row: bool=False):
    for i in range(len(cols)):
        # Use default value of 10 if key is not in col_widths
        col_width = col_widths.get(cols[i], 10)
        if isinstance(header.get(cols[i]), bool):
            col_width = col_widths.get('Bool')
        if header_row:
            to_print = cols[i]
        else:
            to_print = header.get(cols[i])
        if not isinstance(to_print, str):
            to_print = str(to_print)
        # emojis take up two spaces and mess up the column alignment
        # here we subtract num of emojis from col_width
        col_width -= len(re.findall(r'[\U0001f300-\U0001f6ff|\U0001f900-\U0001f9ff]', to_print))
        if i < len(cols)-1:
            formatted_string = f'{truncate(to_print, col_width):<{col_width}} | '
        else:
            formatted_string = f'{to_print}'

        print(terminal.bold(formatted_string) if header_row else formatted_string, end='')
    print()

def truncate(s: str, chars: int):
    if len(s) > chars:
        s = s[:chars-3]+'...'
    return s

# takes the raw email header from the server and returns 
# a dictionary with all the fields
def parse_header(bytes_array):
    email_msg = message_from_bytes(b'\n'.join(bytes_array))
    header = {}
    for key, value in email_msg.items():
        decoded_header = decode_header(value)
        # Convert the decoded parts into a human-readable string
        header[key] = str(make_header(decoded_header))
    return header

# takes a string s, replaces '*' with '.*', escapes other non-alphanumeric
# characters that could be in an email address, and matches it to to_match
# using regex
def wildcard_match(s: str, to_match: str):
    pattern = s.replace("+", "\\+").replace(".", "\\.").replace("*", ".*")
    regex = re.compile(pattern)
    return regex.match(to_match)

# this is the meat of the script that looks through emails 
# in the range of the supplied parameters, displays them,
# and asks to delete them
def get_emails(from_: int, to_: int, show_spam_only: bool=True):
    # error checking to make sure we are going from newest email to oldest
    if to_ > from_:
        to_, from_ = from_, to_
    print(f'searching batch from {str(from_)} to {str(to_+1)}...')
    if show_spam_only:
        print('Displaying only spam:')
    orders = []
    current_batch = []
    # loop through emails in range
    for msg in range(from_, to_, -1):
        try:
            header = parse_header(M.top(msg, 0)[1])
        except ssl.SSLEOFError:
            print("Connection timeout")
            quit()
        header['Index'] = msg
        sender = header.get('From')

        # separate the sender's email address from their name
        search_string = ' <'
        if sender[0] == '\"':
            search_string = '\" <'
            sender = sender[1:]
        if search_string in sender:
            header['Sender Address'] = sender[sender.find(search_string)+len(search_string):len(sender)-1]
            header['From'] = sender[:sender.find(search_string)]
        else: 
            header['Sender Address'] = sender

        # determine if the current email is spam
        header['Probable Spam'] = False
        for key in header:
            if key.startswith('List'):
                header['Probable Spam'] = True
        if 'prefs' in config:
            if 'spam_senders' in config['prefs']:
                for sender in config.get('prefs').get('spam_senders'):
                    if wildcard_match(sender, header.get('Sender Address')):
                        header['Probable Spam'] = True
                        break
            # we check safe senders last. If an email address is in
            # this dictionary, it should override everything else
            if 'safe_senders' in config['prefs']:
                for sender in config.get('prefs').get('safe_senders'):
                    if wildcard_match(sender, header.get('Sender Address')):
                        header['Probable Spam'] = False
                        break

        # the orders list helps us make sure we're not deleting an email about
        # something we ordered (since we may need it later, e.g. to return it)
        if 'order' in header.get('Subject','').lower():
            orders.append(header)
        if header['Probable Spam'] or not show_spam_only:
            column_print(['Index','From','Subject','Sender Address'], header)
            current_batch.append(header)

    if len(current_batch) > 0:
        columns_print(['Index','Probable Spam','From','Subject'], orders)
        if show_spam_only:
            print(f'{len(current_batch)} out of {from_ - to_} marked as spam')
        confirm = input('Delete this batch? ')
        if confirm.lower() == 'y' or confirm.lower() == 'yes':
            for s in current_batch:
                print('deleting '+str(s['Index']))
                try:
                    M.dele(s['Index'])
                except ssl.SSLEOFError:
                    print("Connection timeout")
                    quit()
        elif confirm.lower() == 'quit' or confirm.lower() == 'quit()' or confirm.lower() == 'exit':
            quit()
    else:
        print('No spam to delete')

def get_arg(flag: str, flags: dict):
    return flags.get(flag, {}).get('arg', commands[flags['command']]['flags'].get(flag).get('default'))

def cycle(flags):
    batch_size = int(get_arg('-size', flags))
    show_spam_only = False if flags.get('-all') else True
    num_batches = math.ceil(num_messages / batch_size)
    print(str(num_batches)+' batches in total')
    for batch in range(num_batches):
        from_ = num_messages - (batch * batch_size)
        to_ = max(0, num_messages - (batch * batch_size) - batch_size)
        get_emails(from_, to_, show_spam_only)

def range_cmd(flags):
    from_ = int(get_arg('-from', flags))
    to_ = int(get_arg('-to', flags))
    show_spam_only = False if flags.get('-all') else True
    get_emails(from_, to_, show_spam_only)
def help_command(flags):
    print('List of available commands:')
    for cmd, info in commands.items():
        print(f'\n{cmd}\t{info["description"]}')
        if info["flags"]:
            print('\tFlags:')
            for flag, flag_info in info["flags"].items():
                print(f'\t{flag}\t{flag_info["description"]}')
def validate_flags(command, flags, args):
    while args:
        arg = args.pop(0)
        if arg not in commands[command]['flags']:
            print(f'Invalid flag for command \"{command}\": {arg}')
            return False
        # if the flag requires an argument to follow it
        if commands[command]['flags'][arg]['takes_arg']:
            # if we've reached the end of args, or the next arg is another flag
            if not args or args[0].startswith('-'):
                print(f'Missing argument for flag {arg} in command \"{command}\"')
                return False
            # put the arg into the flags dict for the current flag
            flags[arg] = {'arg': args.pop(0)}
        else:
            flags[arg] = arg
    return True

commands = {
    'help':
    {
        'execute': help_command,
        'description': 'Displays this help message.',
        'flags': {}
    },
    'cycle':
    {
        'execute': cycle,
        'description': f'Cycles through emails in batches',
        'flags':
        {
            '-size':
            {
                'description': f'Set size of batch to cycle through',
                'takes_arg': True,
                'default': 100
            },
            '-all':
            {
                'description': 'Show all emails, don\'t filter spam',
                'takes_arg': False
            }
        }
    },
    'range':
    {
        'execute': range_cmd,
        'description': 'Displays emails in range',
        'flags':
        {
            '-from':
            {
                'description': 'the start of the range',
                'takes_arg': True,
                'default': 1
            },
            '-to':
            {
                'description': 'the end of the range',
                'takes_arg': True,
                'default': 0
            },
            '-all':
            {
                'description': 'Show all emails, don\'t filter spam',
                'takes_arg': False
            }
        }
    },
}

if __name__ == "__main__":
    args = sys.argv[1:]
    pop_domain = ''
    username = ''
    password = ''
    global config
    config = {}
    # if config file doesn't exist, ask for parameters and create file
    config_path = os.path.dirname(os.path.abspath(__file__)) + '/email_filter.conf'
    if not os.path.isfile(config_path):
        config['credentials'] = {}
        config['credentials']['pop_domain'] = input('Enter the host name of your POP mail server: ')
        config['credentials']['username'] = input('Enter your username: ')
        with open(config_path, 'w') as config_file:
            config_file.write(json.dumps(config))
    else:
        with open(config_path, 'r') as config_file:
            config = json.loads(config_file.read())

    password = input('Enter your password: ')
    global M
    try:
        M = poplib.POP3_SSL(config.get('credentials').get('pop_domain'))
    except:
        print("Could not connect to server")
        quit()
    try:
        M.user(config.get('credentials').get('username'))
        M.pass_(password)
    except:
        print("Invalid credentials")
        quit()

    global num_messages
    num_messages = M.stat()[0]
    commands['range']['flags']['-from']['default'] = num_messages
    global col_widths
    col_widths = {
        'Index': len(str(num_messages)),
        'From': 25,
        'Subject': 50,
        'Bool': 5
    }
    print('Login successful.\nTotal messages: ' + str(num_messages))

    # start main loop
    while True:
        user_input = input('\ncommand: ')
        tokens = user_input.split()
        if len(tokens) == 0:
            continue
        command = tokens[0]
        args = tokens[1:] if len(tokens) > 1 else []

        if command in commands:
            flags = {'command': command}
            if validate_flags(command, flags, args):
                commands[command]['execute'](flags)
        else:
            print(f'Unknown command: \"{command}\". Use "help" to see a list of available commands.')