# coding: utf-8
from __future__ import unicode_literals, print_function

from setuptools import setup, find_packages
from cadfael import __version__


with open('README.rst') as f:
    README = f.read()

with open('LICENSE') as f:
    LICENSE = f.read()

setup(
    name='cadfael',
    version=__version__,
    description='Security binary analysis tool; find anomalies',
    long_description=README,
    author='Richard "Lord Coops" Cooper',
    #author_email='',
    url='https://github.com/mountainstorm/Cadfael',
    license=LICENSE,
    packages=find_packages(exclude=('tests', 'docs'))
)
