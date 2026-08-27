#!/usr/bin/env python3
"""Re-indent the agent.py file properly"""

import re

def fix_indentation():
    with open('deezy/core/agent.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped:
            # Empty line - no indentation
            new_lines.append('\n')
            continue
        
        # Count leading spaces
        leading_spaces = len(line) - len(stripped)
        
        # Round to nearest multiple of 4
        new_indent = round(leading_spaces / 4) * 4
        if new_indent == 0 and line.strip():
            new_indent = 4
        
        # Special cases for dedent
        stripped_line = line.lstrip()
        if stripped_line.startswith(('return ', 'raise ', 'break', 'continue', 'pass')):
            # These don't change indent for next line
            pass
        elif stripped.startswith(('else:', 'elif ', 'except', 'finally:')):
            pass
        
        new_line = ' ' * new_indent + stripped
        if new_indent == 0 and stripped:
            new_line = '    ' + stripped  # At least 4 spaces for class methods
        
        new_lines.append(new_line.rstrip('\n') + '\n')
    
    with open('deezy/core/agent_fixed.py', 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    fix_indentation()
    print('Done')

if __name__ == '__main__':
    fix_indentation()