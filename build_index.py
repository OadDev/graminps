import re

with open('/app/frontend_source.html', 'r') as f:
    html = f.read()
with open('/app/new_app_script.js', 'r') as f:
    new_js = f.read()
with open('/app/landing_markup.html', 'r') as f:
    landing = f.read()
with open('/app/dev_markup.html', 'r') as f:
    dev = f.read()

marker = "<script>\n/* ============================================================\n   GRAMIN PAN SEVA — APP STATE & ROUTING"
idx = html.find(marker)
assert idx != -1, "marker not found"
head = html[:idx]

# Insert a hidden React root so the injected CRA bundle mounts without errors
head = re.sub(r'(<body[^>]*>)', r'\1\n<div id="root" style="display:none"></div>', head, count=1)

# Clear the demo password value so users type real credentials
head = head.replace('id="loginPassword" value="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"', 'id="loginPassword" value=""')

# Inject the marketing landing page right before the auth root
head = head.replace('<div id="authRoot">', landing + '\n\n<div id="authRoot" style="display:none">', 1)

# Inject the hidden developer console before the landing page
head = head.replace('<div id="landingRoot">', dev + '\n\n<div id="landingRoot">', 1)

assembled = head + "<script>\n" + new_js + "\n</script>\n</body>\n</html>\n"

with open('/app/frontend/public/index.html', 'w') as f:
    f.write(assembled)

print("written", len(assembled), "bytes")
print("landingRoot present:", 'id="landingRoot"' in assembled)
print("authRoot hidden:", '<div id="authRoot" style="display:none">' in assembled)
print("router present:", 'function route()' in assembled)
