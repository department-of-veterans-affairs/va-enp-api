"""."""

import sys

from loguru import logger


def expensive_func() -> str:
    """.

    Returns
    -------
        str: Yes

    """
    return 'Yes'


logger.remove()

logger.add(sys.stdout, level='DEBUG')
breakpoint()
logger.info('Was this expensive? {} How much did it cost? {}', expensive_func(), '3.50')
