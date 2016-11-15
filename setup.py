#!/usr/bin/python
"""Setup definition for dockpulp.

To install:
    python setup.py install

To install in development mode:
    python setup.py develop

For a comprehensive usage explanation:
    python setup.py --help
"""
import sys
import io
import os
import re
from setuptools import setup


def _simplejson_on_python26():
    if (sys.version_info[0] > 2 or
        (sys.version_info[0] == 2 and
         sys.version_info[1] > 6)):
        return []
    return ['simplejson']


def _read(*names, **kwargs):
    with io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()


def _find_version(*file_paths):
    version_file = _read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]+)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


install_requires = ['requests']
install_requires.extend(_simplejson_on_python26())

setup(
    name="dockpulp",
    version=_find_version("dockpulp", "__init__.py"),
    author="Jay Greguske",
    author_email="jgregusk@redhat.com",
    description=("ReST API Client to Pulp for manipulating docker images"),
    license="GPLv3",
    url="https://github.com/release-engineering/dockpulp.git",
    package_dir={'': '.'},
    packages=['dockpulp'],
    install_requires=install_requires,
    scripts=['bin/dock-pulp.py', 'bin/dock-pulp-bootstrap.py', 'bin/dock-pulp-restore.py'],
    package_data={'': ['conf/dockpulp.conf', 'conf/dockpulpdistributors.json']},
    test_suite="tests",
)
