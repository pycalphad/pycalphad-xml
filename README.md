# pycalphad-xml
XML database plugin for PyCalphad

This package (including the RelaxNG-based schemas that support it) are considered experimental and are likely to change.
We welcome any feedback and encourage you to report issues or suggestions to us on our [GitHub issues page](https://github.com/pycalphad/pycalphad-xml/issues)!

## Installing

```shell
pip install pycalphad-xml
```

## Usage

PyCalphad version 0.10.1 or later will automatically detect this packge as a plugin and load register the XML reader and writer with PyCalphad's `Database` interface.

Databases can be loaded and used as any other supported format:

```python
from pycalphad import Database

dbf = Database("my_db.xml")  # load from file

dbf.to_file("out.xml")  # write to a file
```

## Development versions

To install the development version of `pycalphad-xml`, clone the repository and install it in editable mode with `pip`:

```shell
git clone git@github.com:pycalphad/pycalphad-xml.git
pip install -e .
```
