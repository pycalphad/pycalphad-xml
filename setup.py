
import os
from setuptools import setup


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='pycalphad_xml',
    author='Richard Otis',
    author_email='richard.otis@outlook.com',
    description='XML database plugin for pycalphad',
    packages=['pycalphad_xml'],
    package_data={
        'pycalphad_xml': ['*.rng'],
    },
    license='MIT',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    url='https://pycalphad.org/',
    install_requires=[
        # NOTE: please try to keep any depedencies in alphabetic order so they
        # may be easily compared with other dependency lists
        'importlib_resources',  # drop when pycalphad drops support for Python<3.9
        'lxml',
        'pycalphad>=0.10.0',
    ],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Physics',
        'Topic :: Scientific/Engineering :: Chemistry',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Supported Python versions
        'Programming Language :: Python :: 3',
    ],

)