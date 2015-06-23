#!/usr/bin/python
import sys
from setuptools import setup, Command

setup(
    name = "dockpulp",
    version = "1.11",
    author = "Jay Greguske",
    author_email = "jgregusk@redhat.com",
    description = ("ReST API Client to Pulp for manipulating docker images"),
    license = "GPLv3",
    url = "https://github.com/release-engineering/dockpulp.git",
    package_dir = {'': '.'},
    packages = ['dockpulp'],
    scripts = ['bin/dock-pulp.py', 'bin/dock-pulp-bootstrap.py', 'bin/dock-pulp-restore.py'],
    data_files = [('/etc', ['conf/dockpulp.conf'])],
)
