from setuptools import setup, find_packages
from art import __version__ as version

setup(
    name='gitlab-art',
    version=version,
    description='Gitlab artifact manager',
    url='https://github.com/kosma/art',
    author='Kosma Moczek',
    author_email='kosma@kosma.pl',
    license='WTFPL',
    packages=find_packages(),
    install_requires=[
        'PyYAML',
        'appdirs',
        'click',
        'python-gitlab',
    ],
    entry_points={
        'console_scripts': [
            'art=art.command_line:main',
        ],
    },
)
