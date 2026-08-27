with open('src/pages/HistoryPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the unclosed div
content = content.replace(
    '<div className="font-medium truncate max-w-xs">{task.objective}</td>',
    '{task.objective}</td>'
)

with open('src/pages/HistoryPage.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')