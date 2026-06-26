import re

with open('/app/frontend_source.html', 'r') as f:
    html = f.read()
with open('/app/new_app_script.js', 'r') as f:
    new_js = f.read()

marker = "<script>\n/* ============================================================\n   GRAMIN PAN SEVA — APP STATE & ROUTING"
idx = html.find(marker)
assert idx != -1, "marker not found"
head = html[:idx]

# Insert a hidden React root so the injected CRA bundle mounts without errors
head = re.sub(r'(<body[^>]*>)', r'\1\n<div id="root" style="display:none"></div>', head, count=1)

# Clear the demo password value so users type real credentials
head = head.replace('id="loginPassword" value="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"', 'id="loginPassword" value=""')

assembled = head + "<script>\n" + new_js + "\n</script>\n</body>\n</html>\n"

with open('/app/frontend/public/index.html', 'w') as f:
    f.write(assembled)

print("written", len(assembled), "bytes")
print("root div present:", 'id="root"' in assembled)
print("password cleared:", 'id="loginPassword" value=""' in assembled)
