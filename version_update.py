import os

template_path = 'version_template.py'
output_path = 'DynamicRoutingUpdater/version.py'

# Hent versjon, fjern 'v', og bruk '0.0.0-dev' som fallback for vanlige pushes
raw_version = os.environ.get('PROJECT_VERSION', '0.0.0-dev')
clean_version = raw_version.lstrip('v')

if not clean_version or clean_version == 'unset':
    clean_version = '0.0.0-dev'

with open(template_path, 'r') as template_file:
    template = template_file.read()

output = template.replace('{{VERSION}}', clean_version)

with open(output_path, 'w') as output_file:
    output_file.write(output)