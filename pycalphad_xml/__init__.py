from pycalphad import Database
from pycalphad_xml import parser
Database.register_format("xml", read=parser.read_xml, write=parser.write_xml)