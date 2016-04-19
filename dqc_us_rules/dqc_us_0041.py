# (c) Copyright 2016, XBRL US Inc. All rights reserved.
# See license.md for license information.
# See PatentNotice.md for patent infringement notice.
from .util import messages

import json
import os
import re
import time

from arelle.ModelDtsObject import ModelConcept
from arelle import XbrlConst, ModelXbrl
from arelle.FileSource import openFileStream, saveFile, openFileSource


_CODE_NAME = 'DQC.US.0041'
_RULE_VERSION = '1.1'


ugtDocs = (
    {"year": 2012,
     "namespace": "http://fasb.org/us-gaap/2012-01-31",
     "docLB": "http://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-doc-2012-01-31.xml",  # noqa
     "entryXsd": "http://xbrl.fasb.org/us-gaap/2012/entire/us-gaap-entryPoint-std-2012-01-31.xsd",  # noqa
     },

    {"year": 2013,
     "namespace": "http://fasb.org/us-gaap/2013-01-31",
     "docLB": "http://xbrl.fasb.org/us-gaap/2013/elts/us-gaap-doc-2013-01-31.xml",  # noqa
     "entryXsd": "http://xbrl.fasb.org/us-gaap/2013/entire/us-gaap-entryPoint-std-2013-01-31.xsd",  # noqa
     },

    {"year": 2014,
     "namespace": "http://fasb.org/us-gaap/2014-01-31",
     "docLB": "http://xbrl.fasb.org/us-gaap/2014/elts/us-gaap-doc-2014-01-31.xml",  # noqa
     "entryXsd": "http://xbrl.fasb.org/us-gaap/2014/entire/us-gaap-entryPoint-std-2014-01-31.xsd",  # noqa
     },

    {"year": 2015,
     "namespace": "http://fasb.org/us-gaap/2015-01-31",
     "docLB": "http://xbrl.fasb.org/us-gaap/2015/us-gaap-2015-01-31.zip/us-gaap-2015-01-31/elts/us-gaap-doc-2015-01-31.xml",  # noqa
     "entryXsd": "http://xbrl.fasb.org/us-gaap/2015/us-gaap-2015-01-31.zip/us-gaap-2015-01-31/entire/us-gaap-entryPoint-std-2015-01-31.xsd",  # noqa
     },

    {"year": 2016,
     "namespace": "http://fasb.org/us-gaap/2016-01-31",
     "docLB": "http://xbrl.fasb.org/us-gaap/2016/us-gaap-2016-01-31.zip/us-gaap-2016-01-31/elts/us-gaap-doc-2016-01-31.xml",  # noqa
     "entryXsd": "http://xbrl.fasb.org/us-gaap/2016/us-gaap-2016-01-31.zip/us-gaap-2016-01-31/entire/us-gaap-entryPoint-std-2016-01-31.xsd",  # noqa
     }
)


def _make_cache(
        val, ugt, cntlr, ugt_default_dimensions_json_file
):
    """
    Creates a new caches for the Taxonomy default dimensions

    :param val: ValidateXbrl to be validated
    :type val: :class: '~arelle.ValidateXbrl.ValidateXbrl'
    :param ugt: Taxonomy to check
    :type ugt: str
    :param cntlr: cntlr to save to
    :type cntlr: :class: '~arelle.Cntrl.Cntrl'
    :param ugt_default_dimensions_json_file: location to save json default
        dimensions
    :type ugt_default_dimensions_json_file: str
    :return: no explicit return, but saves caches for dqc_us_0041
    :rtype: None
    """
    started_at = time.time()
    ugt_entry_xsd = ugt["entryXsd"]
    val.usgaapDefaultDimensions = {}
    prior_validate_disclosure_system = (
        val.modelXbrl.modelManager.validateDisclosureSystem
    )
    val.modelXbrl.modelManager.validateDisclosureSystem = False
    calculations_instance = (ModelXbrl.load(
        val.modelXbrl.modelManager,
        openFileSource(ugt_entry_xsd, cntlr),
        _("built us-gaap calculations cache"))  # noqa
    )
    val.modelXbrl.modelManager.validateDisclosureSystem = (
        prior_validate_disclosure_system
    )

    if calculations_instance is None:
        val.modelXbrl.error(
            "arelle:notLoaded",
            _("US-GAAP calculations not loaded: %(file)s"),  # noqa
           modelXbrl=val,
            file=os.path.basename(ugt_entry_xsd)
        )

    else:
        for defaultDimRel in calculations_instance.relationshipSet(
                XbrlConst.dimensionDefault).modelRelationships:
            if isinstance(
                    defaultDimRel.fromModelObject,
                    ModelConcept
            ) and isinstance(
                defaultDimRel.toModelObject,
                ModelConcept
            ):
                from_name = defaultDimRel.fromModelObject.name
                to_name = defaultDimRel.fromModelObject.name
                val.usgaapDefaultDimensions[from_name] = to_name
        json_str = str(json.dumps(
            val.usgaapDefaultDimensions,
            ensure_ascii=False,
            indent=0)
        )  # might not be unicode in 2.7
        # 2.7 gets unicode this way
        saveFile(cntlr, ugt_default_dimensions_json_file, json_str)
        calculations_instance.close()
        del calculations_instance  # dereference closed modelXbrl
    val.modelXbrl.profileStat(
        _("build default dimensions cache"),  # noqa
        time.time() - started_at
    )


def _setup_cache(val):
    """
    Loads the cache into memory, otherwise it builds it. Should only have to
    build it the first time

    :param val: ValidateXbrl to check if it contains errors
    :type val: :class:'~arelle.ValidateXbrl.ValidateXbrl'
    :return: No explicit return, but loads the default dimensions of taxonomies
        into memory
    :rtype: None
    """
    val.linroleDefinitionIsDisclosure = (
        re.compile(r"-\s+Disclosure\s+-\s", re.IGNORECASE)
    )

    val.linkroleDefinitionStatementSheet = (
        re.compile(r"[^-]+-\s+Statement\s+-\s+.*", re.IGNORECASE)
    )  # no restriction to type of statement

    val.ugtNamespace = None
    cntlr = val.modelXbrl.modelManager.cntlr

    for ugt in ugtDocs:
        ugt_namespace = ugt["namespace"]

        if ((ugt_namespace in val.modelXbrl.namespaceDocs and
             len(val.modelXbrl.namespaceDocs[ugt_namespace]) > 0
             )):

            usgaap_doc = os.path.join(
                os.path.dirname(__file__),
                'resources',
                'DQC_US_0041'
            )

            ugt_default_dimensions_json_file = (
                usgaap_doc +
                os.sep +
                "ugt-default-dimensions.json"
            )

            _load_cache(
                val,
                ugt,
                cntlr,
                ugt_default_dimensions_json_file
            )

            return


def _load_cache(
        val, ugt, cntlr, ugt_default_dimensions_json_file
):
    """
    Loads the cached taxonomy default demensions. If the file isn't cached yet
    it will create a new cache

    :param val: ValidateXbrl to be validated
    :type val: :class: '~arelle.ValidateXbrl.ValidateXbrl'
    :param ugt: Taxonomy to check
    :type ugt: str
    :param cntlr: cntlr to load from
    :type cntlr: :class: '~arelle.CntrlWinMain'
    :param ugt_default_dimensions_json_file: location to load json default
        dimensions from
    :type ugt_default_dimensions_json_file: str
    :return: no explicit return, but loads caches for dqc_us_0041
    :rtype: None
    """
    file = None
    try:
        file = openFileStream(
            cntlr,
            ugt_default_dimensions_json_file,
            'rt',
            encoding='utf-8'
        )
        val.usgaapDefaultDimensions = json.load(file)
        file.close()
    except FileNotFoundError:
        if file:
            file.close()

        _make_cache(
            val,
            ugt,
            cntlr,
            ugt_default_dimensions_json_file
        )


def fire_dqc_us_0041_errors(val):
    """
    Fires all the dqc_us_0041 errors returned by _catch_dqc_us_0041_errors

    :param val: ValidateXbrl to check if it contains errors
    :type val: :class:'~arelle.ValidateXbrl.ValidateXbrl'
    :return: No explicit return, but it fires all the dqc_us_0041 errors
    :rtype: None
    """
    _setup_cache(val)

    for error_info in _catch_dqc_us_0041_errors(val):
        axis_name, axis_default_name, def_name = error_info
        val.modelXbrl.error(
            '{}.16'.format(_CODE_NAME),
            messages.get_message(_CODE_NAME),
            axis_name=axis_name,
            axis_default_name=axis_default_name,
            def_name=def_name,
            ruleVersion=_RULE_VERSION
        )


def _default_dimension_mismatch(default_dimension, usgaap_default_dimensions):
    """
    Returns true if the default dimension is not included in the usgaap default
    dimensions

    :param default_dimension: dimension to test if it is a usgaap default
        dimension
    :type: str
    :param usgaap_default_dimensions: list of usgaap taxonomies default
        dimensions
    :type: list
    :return: True if the default dimensions is not included in the usgaap
        default dimensions
    :rtype: bool
    """
    if default_dimension != usgaap_default_dimensions:
        return True
    return False


def _catch_dqc_us_0041_errors(val):
    """
    Returns a tuple containing the parts of the dqc_us_0041 error to be
    displayed

    :param val: ValidateXbrl to check if it contains errors
    :type val: :class:'~arelle.ValidateXbrl.ValidateXbrl'
    :return: all dqc_us_0041 errors
    :rtype: tuple
    """
    rel_set = val.modelXbrl.relationshipSet(
        XbrlConst.dimensionDefault
    ).modelRelationships
    for rel in rel_set:
        rel_to = rel.toModelObject
        rel_from = rel.fromModelObject
        if (_default_dimension_mismatch(
                rel_to.name,
                val.usgaapDefaultDimensions[rel_from.name]
        )):
            yield (rel_from.name,
                   val.usgaapDefaultDimensions[rel_from.name],
                   rel_to.name
                   )

__pluginInfo__ = {
    'name': _CODE_NAME,
    'version': _RULE_VERSION,
    'description': 'All axis defaults should be the same as the axis '
                   'defaults defined in the taxonomy.',
    # Mount points
    'Validate.XBRL.Finally': fire_dqc_us_0041_errors,
}
