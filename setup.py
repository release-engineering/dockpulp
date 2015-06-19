#!/usr/bin/python
import sys
from setuptools import setup, Command

setup(
    name = "dockpulp",
    version = "0.1",
    author = "Release Configuration Management",
    author_email = "rcm-tools@redhat.com",
    description = ("ReST API Client to Pulp for manipulating docker images"),
    license = "GPLv3",
    url = "https://github.com/release-engineering/dockpulp.git",
    package_dir = {'': '.'},
    packages = ['dockpulp'],
    scripts = ['bin/dock-pulp.py'],
    data_files = [('/etc', ['conf/dockpulp.conf'])],
)
