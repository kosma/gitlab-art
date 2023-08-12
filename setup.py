import os
from setuptools import setup, find_packages
from art import __version__ as version

def read_project_file(path):
    proj_dir = os.path.dirname(__file__)
    path = os.path.join(proj_dir, path)
    with open(path, 'r') as f:
        return f.read()

setup(
    name='gitlab-art',
    version=version,
    description='Gitlab artifact manager',
    long_description = read_project_file('README.md'),
    long_description_content_type = 'text/markdown',
    url='https://github.com/kosma/gitlab-art',
    author='Kosma Moczek',
    author_email='kosma@kosma.pl',
    license='WTFPL',
    packages=find_packages(),
    install_requires=[
        'PyYAML',
        'appdirs',
        'click',
        'python-gitlab>=1.12.0',
    ],
    entry_points={
        'console_scripts': [
            'art=art.command_line:main',
        ],
    },
)
