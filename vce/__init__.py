__title__ = 'vce'
__description__ = 'Virtual Constellation Engine.'
__url__ = 'http://www.isi.edu'
__version__ = '0.1.0'
__author__ = 'Marco Paolieri'
__email__ = 'paolieri@usc.edu'
__license__ = 'AGPLv3'
__copyright__ = 'Copyright (C) 2019 Marco Paolieri'

import click
from functools import partial
from .utils import set_logger

click.option = partial(click.option, show_default=True)
set_logger('WARNING')
