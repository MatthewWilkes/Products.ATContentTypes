#  ATContentTypes http://sf.net/projects/collective/
#  Archetypes reimplementation of the CMF core types
#  Copyright (c) 2003-2005 AT Content Types development team
#
# GNU General Public Licence (GPL)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA  02111-1307  USA
#

"""This module contains a mixin-class to support selecting default layout
templates and/or default pages (in the style of default_page/index_html).
The implementation extends TemplateMixin from Archetypes, and implements
the ISelectableBrowserDefault interface from CMFPlone.
"""
__author__  = 'Martin Aspeli <optilude@gmx.net>'
__docformat__ = 'plaintext'

import types

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass

from Acquisition import aq_parent, aq_base

from Products.CMFCore.utils import getToolByName
from Products.CMFCore import CMFCorePermissions

from Products.Archetypes.TemplateMixin import TemplateMixin, TemplateMixinSchema

from Products.ATContentTypes.config import HAS_PLONE2
from Products.ATContentTypes.permission import ModifyViewTemplate

if HAS_PLONE2:
    from Products.CMFPlone.interfaces.BrowserDefault \
        import ISelectableBrowserDefault

from Products.Archetypes.interfaces.templatemixin import ITemplateMixin

try:
    from Products.CMFDynamicViewFTI.fti import DynamicViewTypeInformation
except ImportError:
    from Products.CMFCore.TypesTool import FactoryTypeInformation
    fti_meta_type = FactoryTypeInformation.meta_type
else:
    fti_meta_type = DynamicViewTypeInformation.meta_type


# Set up our schema
BrowserDefaultSchema = TemplateMixinSchema.copy()
BrowserDefaultSchema['layout'].write_permission = ModifyViewTemplate
BrowserDefaultSchema['layout'].vocabulary = 'getAvailableLayouts'
BrowserDefaultSchema['layout'].enforceVocabulary = 0
BrowserDefaultSchema['layout'].widget.visible = {'view' : 'hidden',
                                                 'edit' : 'hidden'}


class BrowserDefaultMixin(TemplateMixin):
    """ Allow the user to select a layout template (in the same way as
        TemplateMixin in Archetypes does), and/or to set a contained
        object's id as a default_page (acting in the same way as index_html)
    """
    if HAS_PLONE2:
        __implements__ = (ISelectableBrowserDefault, ITemplateMixin, )
    else:
        __implements__ = (ITemplateMixin, )
        
    _at_fti_meta_type = fti_meta_type
    aliases = {
        '(Default)' : '(dynamic view)',
        'view' : '(dynamic view)',
        'index.html' : '(dynamic view)',
        'edit' : 'atct_edit',
        'gethtml' : '',
        'mkdir' : '',
        }
    
    default_view = "base_view"
    suppl_views = ()

    security = ClassSecurityInfo()

    security.declareProtected(CMFCorePermissions.View, 'defaultView')
    def defaultView(self, request=None):
        """
        Get the actual view to use. If a default page is set, its id will
        be returned. Else, the current layout's page template id is returned.
        """
        if self.isPrincipiaFolderish and self.getDefaultPage():
            return self.getDefaultPage()
        else:
            return self.getLayout()

    # Note that Plone's browserDefault is very scary. This method should delegate
    # to PloneTool.browserDefault() if at all possible. browserDefault() is
    # aware of IBrowserDefault and will do the right thing wrt. layouts and
    # default pages.

    def __browser_default__(self, request):
        """
        Resolve what should be displayed when viewing this object without an
        explicit template specified. If a default page is set, resolve and
        return that. If not, resolve and return the page template found by
        getLayout().
        """
        # Delegate to PloneTool's version if we have it else, use
        # defaultView(), which will handle the folder/non-folder
        # distinction for us
        if HAS_PLONE2:
            return getToolByName(self, 'plone_utils').browserDefault(self)
        else:
            return self, [self.defaultView(request),]

    # Inherited from TemplateMixin
    # def __call__(self):
    #     """Resolve the current layout template in the current aq context"""
    #

    security.declareProtected(CMFCorePermissions.View, 'getDefaultPage')
    def getDefaultPage(self):
        """
        Return the id of the default page, or None if none is set. The default
        page must be contained within this (folderish) item.
        """
        default = self.getProperty('default_page', '')
        if type(default) in (types.ListType, types.TupleType):
            default = default[0]
        if not default:
            return None
        return default

    security.declareProtected(CMFCorePermissions.View, 'getLayout')
    def getLayout(self, **kw):
        """
        Get the selected layout template. Note that a selected default page
        will override the layout template.
        """
        layout = self.getField('layout').get(self)
        if not layout:
            return self.getDefaultLayout()
        else:
            return layout

    security.declarePublic('canSetDefaultPage')
    def canSetDefaultPage(self):
        """
        Return True if the user has permission to select a default page on this
        (folderish) item, and the item is folderish.
        """
        if not self.isPrincipiaFolderish:
            return False
        mtool = getToolByName(self, 'portal_membership')
        member = mtool.getAuthenticatedMember()
        return member.has_permission(ModifyViewTemplate, self)

    security.declareProtected(ModifyViewTemplate, 'setDefaultPage')
    def setDefaultPage(self, objectId):
        """
        Set the default page to display in this (folderish) object. The objectId
        must be a value found in self.objectIds() (i.e. a contained object).
        This object will be displayed as the default_page/index_html object
        of this (folderish) object. This will override the current layout
        template returned by getLayout(). Pass None for objectId to turn off
        the default page and return to using the selected layout template.
        """
        if self.hasProperty('default_page'):
            if objectId is None:
                self.manage_delProperties(['default_page'])
            else:
                self.manage_changeProperties(default_page = objectId)
        else:
            if objectId is not None:
                self.manage_addProperty('default_page', objectId, 'string')

    security.declareProtected(ModifyViewTemplate, 'setLayout')
    def setLayout(self, layout):
        """
        Set the layout as the current view. 'layout' should be one of the list
        returned by getAvailableLayouts(). If a default page has been set
        with setDefaultPage(), it is turned off by calling setDefaultPage(None).
        """
        self.getField('layout').set(self, layout)
        self.setDefaultPage(None)

    # Inherited from TemplateMixin
    # def getDefaultLayout():
    #    """
    #    Get the default layout template.
    #    """

    security.declarePublic('canSetLayout')
    def canSetLayout(self):
        """
        Return True if the current authenticated user is permitted to select
        a layout.
        """
        mtool = getToolByName(self, 'portal_membership')
        member = mtool.getAuthenticatedMember()
        return member.has_permission(ModifyViewTemplate, self)

    security.declareProtected(CMFCorePermissions.View, 'getAvailableLayouts')
    def getAvailableLayouts(self):
        """
        Get the layouts registered for this object.
        """
        vocab = self._voc_templates()

        # Convert to the list-of-tuples required by the interface so that we're
        # not returning AT-specific DisplayLists
        tuples = []
        for id in vocab.keys():
            tuples.append((id, vocab.getValue(id),))
        return tuples


InitializeClass(BrowserDefaultMixin)
