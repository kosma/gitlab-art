from setuptools import setup, find_packages

setup(
    name='art',
    version='0.1.1',
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
        'requests',
    ],
    entry_points={
        'console_scripts': [
            'art=art.command_line:main',
        ],
    },
)
