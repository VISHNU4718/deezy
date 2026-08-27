with open('src/pages/HistoryPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the unclosed div - replace <div className="font-medium truncate max-w-xs">{task.objective}</td> with {task.objective}</td>
old = '<div className="font-medium truncate max-w-xs">{task.objective}</td>'
new = '{task.objective}</td>'
content = content.replace(old, new)

with open('src/pages/HistoryPage.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')