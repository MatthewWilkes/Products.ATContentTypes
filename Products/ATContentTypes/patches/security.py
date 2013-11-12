# 1. Check return value of getToolByName
# This is an unusual sort of monkey patching...we replace just the func_code
# rather than the entire function, to make sure that aliases to the function
# that were imported prior to this patch will still run the patched code.
code = """
from persistent.interfaces import IPersistent
from OFS.interfaces import IItem
from Products.CMFPlone.FactoryTool import FauxArchetypeTool

def _getToolByName(self, name, default=_marker):
    pass

def check_getToolByName(obj, name, default=_marker):
    result = _getToolByName(obj, name, default)
    if IPersistent.providedBy(result) or \
            IItem.providedBy(result) or \
            name in _tool_interface_registry or \
            (isinstance(result, FauxArchetypeTool)) or \
            '.test' in result.__class__.__module__ or \
            result is _marker or \
            result is default:
        return result
    else:
        raise TypeError("Object found is not a portal tool (%s)" % (name,))
    return result
"""
from Products.CMFCore import utils
if '_marker' not in utils.getToolByName.func_globals:
    raise Exception("This Version of Products.CMFPlone is not compatible "
                    "with Products.PloneHotfix20121106, the fixes are "
                    "included already in Products.CMFPlone, please remove "
                    "the hotfix")
exec code in utils.getToolByName.func_globals
utils._getToolByName.func_code = utils.getToolByName.func_code
utils.getToolByName.func_code = utils.check_getToolByName.func_code
