import re

with open('src/components/ConversationSidebar.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Check paren/brace balance
open_paren = 0
open_brace = 0
for i, char in enumerate(content):
    if char == '(':
        print(f'({i}')
    elif char == ')':
        if open_paren > 0:
            open_paren -= 1
        else:
            print(f'Unmatched ) at {i}')
    elif char == '{':
        print(f'{{ at {i}')
    elif char == '}':
        if open_brace > 0:
            open_brace -= 1
        else:
            print(f'Unmatched }} at {i}')

print(f'Final balance - parens: {open_paren}, braces: {open_brace}')

# Check JSX tag balance
import re
open_tags = 0
close_tags = 0
self_closing = 0
for m in re.finditer(r'<([^/>][^>]*)>', content):
    open_tags += 1
for m in re.finditer(r'</([^>]+)>', content):
    close_tags += 1
for m in re.finditer(r'<[^/>]+/>', content):
    self_closing += 1

print(f'Open tags: {open_tags}, Close tags: {close_tags}, Self-closing: {self_closing}')

# Check the specific area around line 318
lines = content.split('\n')
for i, line in enumerate(content.split('\n')[315:325], 316):
    print(f'{i}: {repr(line)}')