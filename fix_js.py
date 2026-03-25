import os

path = 'static/custom-objects.js'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\`', '`')
content = content.replace('\\${', '${')
content = content.replace('\\$', '$')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed escaping issues in custom-objects.js')
