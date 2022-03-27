from pycalphad.io.tdb import _sympify_string, _process_reference_state, to_interval
from pycalphad import variables as v
from pycalphad import __version__ as pycalphad_version
from symengine import Piecewise, And, Symbol, S
from lxml import etree, objectify
import logging
logger = logging.getLogger(__name__)

# Workaround so this can be imported from other working directory.
# We should use importlib.resources, etc. to package up and refer to schemas.
from pathlib import Path
this_dir = Path(__file__).parent


def convert_math_to_symbolic(math_nodes):
    result = 0.0
    interval_nodes = [x for x in math_nodes if (not isinstance(x, str)) and x.tag == 'Interval']
    string_nodes = [x for x in math_nodes if isinstance(x, str)]
    for math_node in string_nodes:
        # +0 is a hack, for how the function works
        result += _sympify_string(math_node+'+0')
    result += convert_intervals_to_piecewise(interval_nodes)
    result = result.xreplace({Symbol('T'): v.T, Symbol('P'): v.P})
    return result


def convert_intervals_to_piecewise(interval_nodes):
    exprs = []
    conds = []
    for interval_node in interval_nodes:
        if interval_node.attrib['in'] != 'T':
            raise ValueError('Unsupported interval')
        variable = interval_node.attrib['in']
        lower = float(interval_node.attrib.get('lower', '-inf'))
        upper = float(interval_node.attrib.get('upper', 'inf'))
        math_expr = convert_math_to_symbolic([''.join(interval_node.itertext()).replace('\n', '').replace(' ', '').strip()])
        if upper != float('inf'):
            cond = And(lower <= getattr(v, variable, Symbol(variable)), upper > getattr(v, variable))
        else:
            cond = (lower <= getattr(v, variable, Symbol(variable)))
        conds.append(cond)
        exprs.append(math_expr)
    if len(exprs) == 0:
        return 0
    return Piecewise(*(list(zip(exprs, conds)) + [(0, True)]))


def convert_symbolic_to_nodes(sym):
    nodes = []
    if isinstance(sym, Piecewise):
        filtered_args = [(x, cond) for x, cond in zip(*[iter(sym.args)]*2) if not ((cond == S.true) and (x == S.Zero))]
        for expr, cond in filtered_args:
            interval = to_interval(cond)
            lower = str(float(interval.start))
            upper = str(float(interval.end))
            converted_expr_nodes = [x for x in convert_symbolic_to_nodes(expr) if x != '0']
            if lower == '-inf' and upper == 'inf':
                nodes.extend(converted_expr_nodes)
                continue
            elif lower != '-inf' and upper == 'inf':
                interval_node = etree.Element("Interval", attrib={"in": "T", "lower": lower})
            else:
                interval_node = etree.Element("Interval", attrib={"in": "T", "lower": lower, "upper": upper})
            for node in converted_expr_nodes:
                if isinstance(node, str):
                    interval_node.text = node
                else:
                    interval_node.append(node)
            nodes.append(interval_node)

    else:
        str_node = str(sym).replace('log(', 'ln(')
        nodes.append(str_node)
    return nodes


def parse_cef_parameter(param_node):
    order_nodes = param_node.xpath('./Order')
    if len(order_nodes) == 0:
        int_order = 0
    else:
        int_order = int(order_nodes[0].text)
    constituent_array = [t.xpath('./Constituent/@refid') for t in param_node.xpath('./ConstituentArray/Site')]
    return int_order, constituent_array

# Symmetry options handled separately in XML
phase_options = {'ionic_liquid_2SL': 'TwoSublatticeIonicLiquid',
                 'liquid': 'Liquid',
                 'gas': 'Gas',
                 'aqueous': 'Aqueous',
                 'charged_phase': 'Charged'}
inv_phase_options = dict([reversed(i) for i in phase_options.items()])

def _get_single_node(nodes, allow_zero=False):
    """Helper function for when a particular set of nodes returned from `xpath` should have exactly one node.

    If null_case is False,
    """
    if len(nodes) == 1:
        return nodes[0]
    elif len(nodes) == 0 and allow_zero:
        return None
    else:
        raise ValueError(f"Unexpected number of nodes for {nodes}. Got {len(nodes)}, expected {'zero or ' if allow_zero else ''} one")


def parse_model(dbf, phase_name, model_node, parameters):
    species_dict = {s.name: s for s in dbf.species}
    model_type = model_node.attrib["type"]
    site_ratios = [float(m) for m in model_node.xpath('./ConstituentArray/Site/@ratio')]
    if len(site_ratios) == 0:  # i.e. they are not found
        site_ratios = [1.0]  # MQMQA special case: 1 sublattice with 1 mole of "quadruplet" species
    sublattice_model = [s.xpath('./Constituent/@refid') for s in model_node.xpath('./ConstituentArray/Site')]

    model_hints = {}
    magnetic_ordering_nodes = model_node.xpath('./MagneticOrdering')
    for magnetic_ordering_node in magnetic_ordering_nodes:
        if magnetic_ordering_node.attrib['type'] == 'IHJ':
            model_hints['ihj_magnetic_afm_factor'] = float(magnetic_ordering_node.attrib['afm_factor'])
            model_hints['ihj_magnetic_structure_factor'] = float(magnetic_ordering_node.attrib['structure_factor'])
        else:
            raise ValueError('Unknown magnetic ordering model')
    atomic_ordering_nodes = model_node.xpath('./AtomicOrdering')
    for atomic_ordering_node in atomic_ordering_nodes:
        model_hints['ordered_phase'] = str(atomic_ordering_node.attrib['ordered_part'])
        model_hints['disordered_phase'] = str(atomic_ordering_node.attrib['disordered_part'])
    # Simple phase options
    for ipo in inv_phase_options.keys():
        ipo_nodes = model_node.xpath('./'+str(ipo))
        for ipo_node in ipo_nodes:
            model_hints[inv_phase_options[ipo_node.tag]] = True
    # Parameter symmetry options
    symmetry_nodes = model_node.xpath('./Symmetry')
    for symmetry_node in symmetry_nodes:
        model_hints['symmetry_'+str(symmetry_node.attrib['type'])] = True

    # MQMQA hints
    if model_type == "MQMQA":
        model_hints["mqmqa"] = {}
        model_hints["mqmqa"]["type"] = model_node.attrib["version"]
        chemical_groups_hint = {
            "cations": {},
            "anions": {},
        }
        for chemical_group_node in model_node.xpath('./ChemicalGroups'):
            # MQMQA cations and anions
            cation_node = _get_single_node(chemical_group_node.xpath('./Cations'))
            for constituent_node in cation_node.xpath('./Constituent'):
                sp = species_dict[constituent_node.attrib["refid"]]
                chemical_groups_hint["cations"][sp] = int(constituent_node.attrib["groupid"])
            anion_node = _get_single_node(chemical_group_node.xpath('./Anions'))
            for constituent_node in anion_node.xpath('./Constituent'):
                sp = species_dict[constituent_node.attrib["refid"]]
                chemical_groups_hint["anions"][sp] = int(constituent_node.attrib["groupid"])
        model_hints["mqmqa"]["chemical_groups"] = chemical_groups_hint
    else:
        # Non-MQMQA chemical groups
        chemical_groups_node = _get_single_node(model_node.xpath('./ChemicalGroups'), allow_zero=True)
        if chemical_groups_node is not None:
            model_hints["chemical_groups"] = {}
            for constituent_node in chemical_groups_node.xpath('./Constituent'):
                sp = species_dict[constituent_node.attrib["refid"]]
                model_hints["chemical_groups"][sp] = int(constituent_node.attrib["groupid"])

    dbf.add_structure_entry(phase_name, phase_name)
    dbf.add_phase(phase_name, model_hints, site_ratios)
    dbf.add_phase_constituents(phase_name, sublattice_model)

    for param_node in parameters:
        param_data = {}  # optional and keyword data for add_parameter
        param_type = param_node.attrib['type']

        int_order, constituent_array = parse_cef_parameter(param_node)
        if (model_type in "MQMQA") or (param_type == "QKT"):
            # Special MQMQA/QKTO handling, which do not have Redlich-Kister parameters.
            # Redlich-Kister "order" has no meaning
            int_order = None
            # Parameters should not be sorted as the constituent order is related to particular exponents
            constituent_array = [[str(c) for c in lx] for lx in constituent_array]
        else:
            constituent_array = [[str(c) for c in sorted(lx)] for lx in constituent_array]

        # Parameter value
        param_nodes = param_node.xpath('./Interval') + [''.join(param_node.xpath('./text()')).strip()]
        function_obj = convert_math_to_symbolic(param_nodes)

        # TODO: Reference

        # Diffusing species
        diffusing_species_refid = _get_single_node(param_node.xpath('./DiffusingSpecies/@refid'), allow_zero=True)
        if diffusing_species_refid is not None:
            param_data["diffusing_species"] = str(diffusing_species_refid)

        # Special metadata for particular parameter types
        if param_type == "MQMG":
            param_data["zeta"] = float(_get_single_node(param_node.xpath('./Zeta')).text)
            # Assumption that in the model implementation, only the first stoichiometry matters  - this is the only one in the XML representation.
            stoichiometric_factors_node = _get_single_node(param_node.xpath('./StoichiometricFactors'))
            param_data["stoichiometry"] = list(map(float, stoichiometric_factors_node.text.split()))
        elif param_type == "MQMZ":
            coordinations_node = _get_single_node(param_node.xpath('./Coordinations'))
            param_data["coordinations"] = list(map(float, coordinations_node.text.split()))
            function_obj = None  # special MQMQA handling - no symbolic parameter value, so ensure it cannot exist
        elif param_type == "MQMX":
            param_data["mixing_code"] = _get_single_node(param_node.xpath('./MixingCode')).attrib["type"]
            exponents_node = _get_single_node(param_node.xpath('./Exponents'))
            param_data["exponents"] = list(map(float, exponents_node.text.split()))
            additional_mixing_constituent_refid = _get_single_node(param_node.xpath('./AdditionalMixingConstituent/@refid'), allow_zero=True)
            if additional_mixing_constituent_refid is not None:
                param_data["additional_mixing_constituent"] = species_dict[str(additional_mixing_constituent_refid)]
                param_data["additional_mixing_exponent"] = float(_get_single_node(param_node.xpath('./AdditionalMixingExponent')).text)
            else:
                param_data["additional_mixing_constituent"] = v.Species(None)
                param_data["additional_mixing_exponent"] = 0  # Arbitrary
        elif param_type == "QKT":
            exponents_node = _get_single_node(param_node.xpath('./Exponents'))
            param_data["exponents"] = list(map(float, exponents_node.text.split()))

        dbf.add_parameter(param_type, phase_name, constituent_array, int_order, function_obj, force_insert=False, **param_data)


def _setitem_raise_duplicates(dictionary, key, value):
    if key in dictionary:
        raise ValueError("Database contains duplicate FUNCTION {}".format(key))
    dictionary[key] = value


def read_xml(dbf, fd):
    parser = etree.XMLParser(load_dtd=False,
                             no_network=True)
    tree = etree.parse(fd, parser=parser)
    relaxng = etree.RelaxNG(etree.parse(this_dir / 'database.rng'))
    if not relaxng.validate(tree):
        logger.warn(relaxng.error_log)
    root = tree.getroot()

    for child in root:
        if child.tag == 'ChemicalElement':
            element = str(child.attrib['id'])
            dbf.species.add(v.Species(element, {element: 1}, charge=0))
            dbf.elements.add(element)
            _process_reference_state(dbf, element, child.attrib['reference_phase'],
                                     float(child.attrib['mass']), float(child.attrib['H298']), float(child.attrib['S298']))
        elif child.tag == 'Species':
            species = str(child.attrib['id'])
            constituent_dict = {}
            species_charge = float(child.attrib.get('charge', 0))
            constituent_nodes = child.xpath('./ChemicalElement')
            for constituent_node in constituent_nodes:
                el = constituent_node.attrib['refid']
                ratio = float(constituent_node.attrib['ratio'])
                constituent_dict[el] = ratio
            dbf.species.add(v.Species(species, constituent_dict, charge=species_charge))
        elif child.tag == 'Expr':
            function_name = str(child.attrib['id'])
            function_obj = convert_intervals_to_piecewise(child)
            _setitem_raise_duplicates(dbf.symbols, function_name, function_obj)
        elif child.tag == 'Phase':
            model_nodes = child.xpath('./Model')
            if len(model_nodes) == 0:
                continue
            model_node = model_nodes[0]
            phase_name = child.attrib['id']
            parameters = child.xpath('./Parameter')
            if model_node.attrib['type'] in ("MQMQA", "CEF"):
                parse_model(dbf, phase_name, model_node, parameters)
    dbf.process_parameter_queue()


def write_xml(dbf, fd, require_valid=True):
    root = objectify.Element("Database", version=str(0))
    metadata = objectify.SubElement(root, "metadata")
    writer = objectify.SubElement(metadata, "writer")
    writer._setText('pycalphad ' + str(pycalphad_version))
    phase_nodes = {}
    for element in sorted(dbf.elements):
        ref = dbf.refstates.get(element, {})
        refphase = ref.get('phase', 'BLANK')
        mass = ref.get('mass', 0.0)
        H298 = ref.get('H298', 0.0)
        S298 = ref.get('S298', 0.0)
        objectify.SubElement(root, "ChemicalElement", id=str(element), mass=str(mass),
                             reference_phase=refphase, H298=str(H298), S298=str(S298))
    for species in sorted(dbf.species, key=lambda s: s.name):
        if species.name not in dbf.elements:
            species_node = objectify.SubElement(root, "Species", id=str(species.name), charge=str(species.charge))
            for el_name, ratio in sorted(species.constituents.items(), key=lambda t: t[0]):
                objectify.SubElement(species_node, "ChemicalElement", refid=str(el_name), ratio=str(ratio))
    for name, expr in sorted(dbf.symbols.items()):
        expr_node = objectify.SubElement(root, "Expr", id=str(name))
        converted_nodes = convert_symbolic_to_nodes(expr)
        for node in converted_nodes:
            if isinstance(node, str):
                expr_node._setText(node)
            else:
                expr_node.append(node)
    for name, phase_obj in sorted(dbf.phases.items()):
        if phase_nodes.get(name, None) is None:
            phase_nodes[name] = objectify.SubElement(root, "Phase", id=str(name))
        # All model hints must be consumed for the writing to be considered successful
        model_hints = phase_obj.model_hints.copy()
        possible_options = set(phase_options.keys()).intersection(model_hints.keys())
        # TODO: extra parameters for QKTO
        if "mqmqa" in model_hints:
            # MQMQA model
            hint = model_hints["mqmqa"]
            model_node = objectify.SubElement(phase_nodes[name], "Model", type="MQMQA", version=hint["type"])

            # ConstituentArray (MQMConstituentArray)
            constit_array_node = objectify.SubElement(model_node, "ConstituentArray")
            subl_idx = 0
            # Don't loop over sublattices, they are reflective of cation/anion sublattices for MQMQA
            for constituents in phase_obj.constituents:
                # Site ratios are not relevant for MQMQA phases
                site_node = objectify.SubElement(constit_array_node, "Site", id=str(subl_idx))
                for constituent in sorted(constituents, key=str):
                    objectify.SubElement(site_node, "Constituent", refid=str(constituent))
                subl_idx += 1

            # ChemicalGroups
            chemical_groups_node = objectify.SubElement(model_node, "ChemicalGroups")
            cation_node = objectify.SubElement(chemical_groups_node, "Cations")
            for constituent, group_id in hint["chemical_groups"]["cations"].items():
                    objectify.SubElement(cation_node, "Constituent", refid=str(constituent), groupid=str(group_id))
            anion_node = objectify.SubElement(chemical_groups_node, "Anions")
            for constituent, group_id in hint["chemical_groups"]["anions"].items():
                    objectify.SubElement(anion_node, "Constituent", refid=str(constituent), groupid=str(group_id))
            del model_hints["mqmqa"]
        else:
            model_node = objectify.SubElement(phase_nodes[name], "Model", type="CEF")
            constit_array_node = objectify.SubElement(model_node, "ConstituentArray")
            subl_idx = 0
            for site_ratio, constituents in zip(phase_obj.sublattices, phase_obj.constituents):
                site_node = objectify.SubElement(constit_array_node, "Site", id=str(subl_idx), ratio=str(site_ratio))
                for constituent in sorted(constituents, key=str):
                    objectify.SubElement(site_node, "Constituent", refid=str(constituent))
                subl_idx += 1
            # IHJ model
            if 'ihj_magnetic_afm_factor' in model_hints.keys():
                objectify.SubElement(model_node, "MagneticOrdering",
                    type="IHJ", structure_factor=str(model_hints['ihj_magnetic_structure_factor']),
                    afm_factor=str(model_hints['ihj_magnetic_afm_factor']))
                del model_hints['ihj_magnetic_afm_factor']
                del model_hints['ihj_magnetic_structure_factor']
            # Two-part atomic ordering
            if ('ordered_phase' in model_hints.keys()):
                objectify.SubElement(model_node, "AtomicOrdering",
                    ordered_part=str(model_hints['ordered_phase']),
                    disordered_part=str(model_hints['disordered_phase']))
                del model_hints['ordered_phase']
                del model_hints['disordered_phase']
            # Symmetry options
            symmetry_node = None
            if ('symmetry_FCC_4SL' in model_hints.keys()):
                symmetry_node = objectify.SubElement(model_node, "Symmetry", type="FCC_4SL")
                del model_hints['symmetry_FCC_4SL']
            if ('symmetry_BCC_4SL' in model_hints.keys()):
                if symmetry_node is not None:
                    raise ValueError('Multiple parameter symmetry options specified')
                del model_hints['symmetry_BCC_4SL']
            # ChemicalGroups
            if "chemical_groups" in model_hints:
                chemical_groups_node = objectify.SubElement(model_node, "ChemicalGroups")
                for constituent, group_id in model_hints["chemical_groups"].items():
                        objectify.SubElement(chemical_groups_node, "Constituent", refid=str(constituent), groupid=str(group_id))
                del model_hints["chemical_groups"]
            # Simple phase options
            for possible_option in possible_options:
                objectify.SubElement(model_node, phase_options[possible_option])
                del model_hints[possible_option]
        if len(model_hints) > 0:
            # Some model hints were not properly consumed
            raise ValueError('Not all model hints are supported: {}'.format(model_hints))

    for param in dbf._parameters.all():
        phase_name = param['phase_name']
        # Create phase implicitly if not defined
        if phase_nodes.get(phase_name, None) is None:
            phase_nodes[phase_name] = objectify.SubElement(root, "Phase", id=str(phase_name))
        phase_node = phase_nodes[phase_name]
        param_node = objectify.SubElement(phase_node, "Parameter", type=str(param['parameter_type']))
        if param.get("parameter_order") is not None:
            order_node = objectify.SubElement(param_node, "Order")
            order_node._setText(str(param['parameter_order']))
        # Constituent array
        constit_array_node = objectify.SubElement(param_node, "ConstituentArray")
        subl_idx = 0
        for constituents in param['constituent_array']:
            site_node = objectify.SubElement(constit_array_node, "Site", refid=str(subl_idx))
            for constituent in constituents:
                objectify.SubElement(site_node, "Constituent", refid=str(constituent))
            subl_idx += 1
        if param['diffusing_species'] != v.Species(None):
            objectify.SubElement(param_node, "DiffusingSpecies", refid=str(param['diffusing_species']))
        # Handle unique aspects of MQMQA parameters
        if param["parameter_type"] == "MQMG":
            objectify.SubElement(param_node, "Zeta")._setText(str(param["zeta"]))
            objectify.SubElement(param_node, "StoichiometricFactors")._setText(" ".join(map(str, param["stoichiometry"])))
        elif param["parameter_type"] == "MQMZ":
            coordinations_node = objectify.SubElement(param_node, "Coordinations")
            coordinations_node._setText(" ".join(map(str, param["coordinations"])))
        elif param["parameter_type"] == "MQMX":
            objectify.SubElement(param_node, "MixingCode", type=param["mixing_code"])
            objectify.SubElement(param_node, "Exponents")._setText(" ".join(map(str, param["exponents"])))
            if param["additional_mixing_constituent"] != v.Species(None):
                objectify.SubElement(param_node, "AdditionalMixingConstituent", refid=str(param["additional_mixing_constituent"]))
                objectify.SubElement(param_node, "AdditionalMixingExponent")._setText(str(param["additional_mixing_exponent"]))
        elif param["parameter_type"] == "QKT":
            objectify.SubElement(param_node, "Exponents")._setText(" ".join(map(str, param["exponents"])))

        if param.get("parameter") is not None:
            nodes = convert_symbolic_to_nodes(param['parameter'])
            for node in nodes:
                if isinstance(node, str):
                    param_node._setText(node)
                else:
                    param_node.append(node)
        # TODO: param['reference']
    objectify.deannotate(root, xsi_nil=True)
    etree.cleanup_namespaces(root)

    # Validate
    relaxng = etree.RelaxNG(etree.parse(this_dir / 'database.rng'))
    if not relaxng.validate(root):
        if require_valid:
            raise ValueError("Failed to validate constructed database", relaxng.error_log)
        else:
            logger.warning("Failed to validate constructed database:\n %s", str(relaxng.error_log))

    fd.write('<?xml version="1.0"?>\n')
    # XXX: href needs to be changed
    fd.write('<?xml-model href="database.rng" schematypens="http://relaxng.org/ns/structure/1.0" type="application/xml"?>\n')
    fd.write(etree.tostring(root, pretty_print=True).decode("utf-8"))
