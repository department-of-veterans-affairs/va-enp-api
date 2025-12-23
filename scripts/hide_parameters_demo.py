"""Demo hide_parameters behavior using in-memory SQLite.

to test: poetry run python -i scripts/hide_parameters_demo.py
"""

import logging
import sys

from sqlalchemy import create_engine, text

EXAMPLE_VALUE = 'example-value'


def run_demo(hide_parameters: bool) -> None:
    """Run the demo with the requested hide_parameters setting."""
    engine = create_engine('sqlite://', echo=True, hide_parameters=hide_parameters)
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT :value AS value'), {'value': EXAMPLE_VALUE})
            conn.execute(text('SELECT * FROM missing_table WHERE id=:value'), {'value': EXAMPLE_VALUE})
    except Exception as exc:
        print(f'\n--- hide_parameters={hide_parameters} error ---')
        print(exc)
    finally:
        engine.dispose()


def main() -> None:
    """Run the demo for both hide_parameters settings."""
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    run_demo(False)
    run_demo(True)


if __name__ == '__main__':
    if not sys.flags.interactive:
        main()
