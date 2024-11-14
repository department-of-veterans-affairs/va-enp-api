"""Script to automatically generate MkDocs for modules located in app/ directory."""

from pathlib import Path

import mkdocs_gen_files

docs_path = Path('docs')
docs_path.mkdir(parents=True, exist_ok=True)

nav = mkdocs_gen_files.Nav()

src = Path(__file__).parent.parent / 'app'

for path in sorted(src.rglob('*.py')):
    module_path = path.relative_to(src).with_suffix('')
    doc_path = path.relative_to(src).with_suffix('.md')
    full_doc_path = Path('', doc_path)
    parts = list(module_path.parts)

    if parts[-1] == '__init__':
        with open(path) as f:
            if not any('def' in line for line in f):
                continue
        parts = parts[:-1]
    elif parts[-1] == '__main__':
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, 'w') as fd:
        identifier = '.'.join(parts)
        print(f'::: app.{identifier}', file=fd)

    mkdocs_gen_files.set_edit_path(full_doc_path, Path('../') / path)

with mkdocs_gen_files.open('index.md', 'w') as nav_file:
    nav_file.write('# Code Reference\n\n')
    nav_file.write(
        'Welcome to the project documentation. Below, you can find the navigation to the code reference pages:\n\n'
    )
    nav_file.writelines(nav.build_literate_nav())
    nav_file.write('\n\n### Additional Resources\n')
    nav_file.write(
        '- [Wiki Documentation on GitHub](https://github.com/department-of-veterans-affairs/va-enp-api/wiki)\n'
    )
