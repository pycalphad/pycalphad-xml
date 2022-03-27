# pycalphad-xml
XML database plugin for PyCalphad

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

dbf.to_file("out.xml")  # write to a fil
```
