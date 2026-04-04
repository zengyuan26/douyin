#!/usr/bin/env python3
with open('services/keyword_library_generator.py', 'rb') as f:
    data = f.read()

# The problematic string in bytes - line 47 has " instead of \" at two places
# Pattern: "...没有反应"...  and "...有什么区别"...
old = b'没有反应"\xe3\x80\x81"\xe5\x96\x9d\xe5\xae\x8c\xe8\x85\xb9'
new = b'没有反应\\"\xe3\x80\x81\\"\xe5\x96\x9d\xe5\xae\x8c\xe8\x85\xb9'

if old in data:
    data = data.replace(old, new)
    print('Found and replaced')
else:
    print('NOT FOUND - checking raw bytes')
    # Let's find the context
    idx = data.find(b'\xe6\xb2\xa1\xe6\x9c\x89\xe5\x8f\x8d\xe5\xba\x94')
    if idx >= 0:
        print('Context:', repr(data[idx-5:idx+30]))

with open('services/keyword_library_generator.py', 'wb') as f:
    f.write(data)
print('Done')
