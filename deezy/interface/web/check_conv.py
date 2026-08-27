with open('src/components/ConversationSidebar.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the problematic area
idx = content.find('filteredConversations.map(conv => (')
if idx >= 0:
    print('Found map at:', idx)
    # Print from map start to end of component
    print(repr(content[idx:idx+3000]))