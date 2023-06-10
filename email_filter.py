import os
import poplib
import sys
import terminal
import json
from email import message_from_bytes
from email.header import decode_header, make_header
from typing import List

def columns_print(cols: List[str], headers: List[dict]):
    if len(headers) > 0:
        print()
        column_print(cols, headers[0], True)
        for header in headers:
            column_print(cols, header)

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

def parse_header(bytes_array):
    email_msg = message_from_bytes(b'\n'.join(bytes_array))
    header = {}
    for key, value in email_msg.items():
        decoded_header = decode_header(value)
        # Convert the decoded parts into a human-readable string
        header[key] = str(make_header(decoded_header))
    return header

def get_emails(from_: int, to_: int):
    print('batch from '+str(from_)+' to '+str(to_))
    orders = []
    current_batch = []
    for msg in range(from_, to_, -1):
        header = parse_header(M.top(msg, 0)[1])
        header['Index'] = msg
        sender = header.get('From')

        # separate the sender's email address from their name
        search_string = ' <'
        if sender[0] == '\'':
            search_string = '\' <'
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
        for sender in config.get('prefs').get('spam_senders'):
            if sender == header.get('Sender Address'):
                header['Probable Spam'] = True

        # this is to make sure that if we got an email about
        # something we ordered (that way may need later, e.g. to return it)
        # that we see it and don't accidentally delete it
        if 'order' in header['Subject'].lower():
            orders.append(header)
        if header['Probable Spam'] or not show_spam_only:
            column_print(['Index','From','Subject','Sender Address'], header)
            current_batch.append(header)

    columns_print(['Index','Probable Spam','From','Subject'], orders)

    if len(current_batch) > 0:
        confirm = input('Delete this batch? ')
        if confirm.lower() == 'y' or confirm.lower() == 'yes':
            for s in current_batch:
                print('deleting '+str(s['Index']))
                M.dele(s['Index'])
        elif confirm.lower() == 'quit' or confirm.lower() == 'quit()' or confirm.lower() == 'exit':
            quit()
    else:
        print('No spam to delete')

def main():
    # these should be set by user
    cycle = True  # setting this to True cycles through your entire inbox, in groups of group_size
    global show_spam_only
    show_spam_only = True   #if you turn this to false, it shows and deletes ALL emails, not just spam
    group_size = 100 # this is the size of the batch for each cycle

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


    numMessages = M.stat()[0]
    global col_widths
    col_widths = {
        'Index': len(str(numMessages)),
        'From': 25,
        'Subject': 50,
        'Bool': 5
    }
    print('total messages ' + str(numMessages))

    if cycle:
        print(str(int((numMessages-1)/group_size+1))+' groups in total')
        for group in range(0, int((numMessages-1)/group_size+1)):
            from_ = numMessages-1-(group*group_size)
            to_ = max(1,numMessages-1-(group*group_size)-group_size)
            get_emails(from_, to_)
    else:
        get_emails(13210, 13207)

main()