import pytest
from pycalphad import Database, Model, calculate, variables as v
from pycalphad.models.model_mqmqa import ModelMQMQA
from pycalphad.tests.fixtures import select_database, load_database
from pycalphad.tests.test_energy import check_energy

@pytest.mark.xfail(reason="SymEngine is incorrect in equality comparison for expressions")
# e.g. these are not equal:
# this Piecewise((4.0*U1ALNI, And(T < 6000.0, 298.15 <= T)), (0, True))
# other Piecewise((U1ALNI*4.0, And(T < 6000.0, 298.15 <= T)), (0, True))
@select_database("alni_dupin_2001.tdb")
def test_tdb_to_xml_roundtrip(load_database):
    """Test that a TDB can be round-tripped to/from XML and compare equal"""
    dbf_tdb = load_database()
    dbf_xml = Database.from_string(dbf_tdb.to_string(fmt="xml"), fmt="xml")
    assert dbf_tdb == dbf_xml


@select_database("alni_dupin_2001.tdb")
def test_tdb_to_xml_to_xml_roundtrip(load_database):
    """Test that an XML can be roundtripped to XML"""
    dbf_tdb = load_database()
    dbf_xml = Database.from_string(dbf_tdb.to_string(fmt="xml"), fmt="xml")
    dbf_xml_2 = Database.from_string(dbf_xml.to_string(fmt="xml"), fmt="xml")
    assert dbf_xml == dbf_xml_2


@select_database("Kaye_Pd-Ru-Tc-Mo.dat")
def test_QKTO_dat_to_xml_to_roundtrip(load_database):
    """Test that a DAT with QKTO can be round-tripped to/from XML and compare equal"""
    dbf_dat = load_database()
    dbf_xml = Database.from_string(dbf_dat.to_string(fmt="xml"), fmt="xml")
    assert dbf_dat == dbf_xml


@select_database("Shishin_Fe-Sb-O-S_slag.dat")
def test_MQMQA_xml_roundtrip_equality(load_database):
    """Test that loading a DAT file with MQMQA model compares equal"""
    dbf_dat = load_database()
    dbf_xml = Database.from_string(dbf_dat.to_string(fmt="xml"), fmt="xml")
    assert dbf_dat == dbf_xml


@select_database("Shishin_Fe-Sb-O-S_slag.dat")
def test_MQMQA_xml2xml_roundtrip_equality(load_database):
    """Test that loading a DAT file with MQMQA model compares equal"""
    dbf_dat = load_database()
    dbf_xml = Database.from_string(dbf_dat.to_string(fmt="xml"), fmt="xml")
    dbf_xml_2 = Database.from_string(dbf_xml.to_string(fmt="xml"), fmt="xml")
    assert dbf_xml_2 == dbf_xml


@select_database("Shishin_Fe-Sb-O-S_slag.dat")
def test_xml_roundrip_MQMQA_SUBQ_Q_mixing(load_database):
    """Same test as test_MQMQA_SUBQ_Q_mixing_1000K_FACTSAGE, but using a database after roundtripping to XML"""
    dbf_DAT = load_database()

    dbf = Database.from_string(dbf_DAT.to_string(fmt="xml"), fmt="xml")

    FE2 = v.Species("FE2++2.0", constituents={"FE": 2.0}, charge=2)
    FE3 = v.Species("FE3++3.0", constituents={"FE": 3.0}, charge=3)
    SB3 = v.Species("SB3++3.0", constituents={"SB": 3.0}, charge=3)
    O = v.Species("O-2.0", constituents={"O": 1.0}, charge=-2)
    S = v.Species("S-2.0", constituents={"S": 1.0}, charge=-2)
    mod = ModelMQMQA(dbf, ["FE", "SB", "O", "S"], "SLAG-LIQ")

    assert FE2 in mod.cations
    assert FE3 in mod.cations
    assert SB3 in mod.cations
    assert O in mod.anions
    assert S in mod.anions

    subs_dict = {  # FactSage site fractions (Fe2 quadruplet fractions not printed, I assumed 1e-30)
        mod._X_ijkl(FE2,FE2,O,O): 1e-30,
        mod._X_ijkl(FE3,FE3,O,O): 5.5018E-03,
        mod._X_ijkl(SB3,SB3,O,O): 0.26528,
        mod._X_ijkl(FE2,FE3,O,O): 1e-30,
        mod._X_ijkl(FE2,SB3,O,O): 1e-30,
        mod._X_ijkl(FE3,SB3,O,O): 7.6407E-02,
        mod._X_ijkl(FE2,FE2,S,S): 1e-30,
        mod._X_ijkl(FE3,FE3,S,S): 0.26528,
        mod._X_ijkl(SB3,SB3,S,S): 5.5018E-03,
        mod._X_ijkl(FE2,FE3,S,S): 1e-30,
        mod._X_ijkl(FE2,SB3,S,S): 1e-30,
        mod._X_ijkl(FE3,SB3,S,S): 7.6407E-02,
        mod._X_ijkl(FE2,FE2,O,S): 1e-30,
        mod._X_ijkl(FE3,FE3,O,S): 7.6407E-02,
        mod._X_ijkl(SB3,SB3,O,S): 7.6407E-02,
        mod._X_ijkl(FE2,FE3,O,S): 1e-30,
        mod._X_ijkl(FE2,SB3,O,S): 1e-30,
        mod._X_ijkl(FE3,SB3,O,S): 0.15281,
        v.T: 1000.0,
    }
    print(mod.GM.subs(subs_dict))
    check_energy(mod, subs_dict, -131831.0, mode="sympy")  # FactSage energy, from Max


def test_exprs_without_intervals_are_read():
    XML_STR = """<?xml version="1.0"?>
    <?xml-model href="database.rng" schematypens="http://relaxng.org/ns/structure/1.0" type="application/xml"?>
    <Database version="0">
      <ChemicalElement id="H" mass="1.0" reference_phase="GAS" H298="0.0" S298="0.0"/>
      <Expr id="VV0000"><Interval in="T" lower="1.0" upper="6000.0">10000</Interval></Expr>
      <Expr id="VV0001">10000</Expr>
      <Phase id="F(S)"><Model type="CEF"><ConstituentArray><Site id="0" ratio="1.0"><Constituent refid="H"/></Site></ConstituentArray></Model></Phase>
    </Database>
    """
    db = Database.from_string(XML_STR, fmt="xml")

    assert db.symbols["VV0000"].args[0] == 10000.0
    assert db.symbols["VV0001"] == 10000.0