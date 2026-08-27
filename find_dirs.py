import os
for root, dirs, files in os.walk('.'):
    for d in dirs:
        if 'interface' in d or 'web' in d or 'plugins' in d:
            print(os.path.join(root, d))