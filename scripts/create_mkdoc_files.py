"""Script to automatically generate MkDocs for modules located in app/ directory."""

from pathlib import Path

import mkdocs_gen_files

docs_path = Path('docs')

# Delete all previous files in `/docs` path.
if docs_path.exists():
    for old_file in docs_path.glob('**/*'):
        if old_file.is_file():
            old_file.unlink()

# Create the docs directory if it does not exist.
docs_path.mkdir(parents=True, exist_ok=True)

nav = mkdocs_gen_files.Nav()

src = Path(__file__).parent.parent / 'app'

# Iterate thru all .py files in `/app`.
for path in sorted(src.rglob('*.py')):
    # Get the module path and documentation path relative to the source directory.
    module_path = path.relative_to(src).with_suffix('')
    doc_path = path.relative_to(src).with_suffix('.md')
    full_doc_path = Path('', doc_path)
    parts = list(module_path.parts)

    # Skip __init__.py files if they do not contain any method definitions.
    if parts[-1] == '__init__':
        with open(path) as f:
            if not any('def' in line for line in f):
                continue
        parts = parts[:-1]
    # Skip all __main__.py files
    elif parts[-1] == '__main__':
        continue

    # Add the Python module to the navigation structure.
    nav[parts] = doc_path.as_posix()

    # Create the MkDocs documentation file for the Python module.
    with mkdocs_gen_files.open(full_doc_path, 'w') as fd:
        identifier = '.'.join(parts)
        print(f'::: app.{identifier}', file=fd)

    # Set the edit path for the generated documentation file.
    mkdocs_gen_files.set_edit_path(full_doc_path, Path('../') / path)

with mkdocs_gen_files.open('index.md', 'w') as nav_file:
    nav_file.write('# Code Reference\n')
    nav_file.write('## How to use MkDocs\n\n')
    nav_file.write(
        'Please view documentation on how to use MkDocs for this project [here.](https://github.com/department-of-veterans-affairs/va-enp-api/wiki)\n\n'
    )
    nav_file.write('## Navigation\n')
    nav_file.write('Below, you can find the navigation to the code reference pages:\n\n')
    nav_file.writelines(nav.build_literate_nav())
