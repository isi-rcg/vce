#!/usr/bin/env python
# -*- coding: utf-8 -*-

# https://raw.githubusercontent.com/kennethreitz/setup.py/master/setup.py

import io
import os
from setuptools import find_packages, setup
from vce import __title__, __description__, __url__, __version__, \
    __author__, __email__, __license__


NAME = __title__.lower()
VERSION = __version__
DESCRIPTION = __description__
URL = __url__
AUTHOR = __author__
EMAIL = __email__

REQUIRED = [
    'requests',
    'influxdb',
    'responder',
    'click',
    'tcconfig',
    'netifaces',
    'strictyaml',
    'influxdb',
    'matplotlib',
    'jinja2',
    'pyqt5',
    'Cartopy',
    'scipy'
]

# Import the README and use it as the long-description.
# Note: 'README.rst' must be present in your MANIFEST.in file
here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    LONG_DESCRIPTION = '\n' + f.read()

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    entry_points={
        'console_scripts': ['%s = %s.__main__:main' % (NAME, NAME)],
    },
    install_requires=REQUIRED,
    package_data={
        'vce': ['templates/*']
    },
    include_package_data=True,
    license=__license__,
    classifiers=[
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython'
    ]
)
