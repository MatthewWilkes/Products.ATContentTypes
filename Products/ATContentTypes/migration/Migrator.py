"""Migration tools for ATContentTypes

Migration system for the migration from CMFDefault/Event types to archetypes
based CMFPloneTypes (http://sf.net/projects/collective/).

Copyright (c) 2004-2005, Christian Heimes and contributors
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 * Neither the name of the author nor the names of its contributors may be used
   to endorse or promote products derived from this software without specific
   prior written permission.
"""

from copy import copy

from Products.CMFCore.utils import getToolByName
from Acquisition import aq_base
from Acquisition import aq_parent
from Acquisition import aq_inner
from DateTime import DateTime
from Persistence import PersistentMapping
from OFS.Uninstalled import BrokenClass
from OFS.IOrderSupport import IOrderedContainer

from Products.ATContentTypes.migration.common import *
from Products.ATContentTypes.migration.common import _createObjectByType

_marker = []

# Dublin Core mapping
# accessor, mutator, fieldname
DC_MAPPING = (
    ('Title', 'setTitle',                   None),
    ('Creator', None,                         None),
    ('Subject', 'setSubject',               'subject'),
    ('Description', 'setDescription',       'description'),
    ('Publisher', None,                       None),
    ('Contributors', 'setContributors',     'contributors'),
    ('Date', None,                            None),
    ('CreationDate', None,                    None),
    ('EffectiveDate', 'setEffectiveDate',   'effectiveDate'),
    ('ExpirationDate', 'setExpirationDate', 'expirationDate'),
    ('ModificationDate', None,                None),
    ('Type', None,                            None),
    ('Format', 'setFormat',                 None),
    ('Identifier', None,                      None),
    ('Language', 'setLanguage',             'language'),
    ('Rights', 'setRights',                 'rights'),

    # allowDiscussion is not part of the official DC metadata set
    #('allowDiscussion','isDiscussable','allowDiscussion'),
  )

# Mapping used from DC migration
METADATA_MAPPING = []
for accessor, mutator, field in DC_MAPPING:
    if accessor and mutator:
        METADATA_MAPPING.append((accessor, mutator))

def copyPermMap(old):
    """bullet proof copy
    """
    new = PersistentMapping()
    for k,v in old.items():
        nk = copy(k)
        nv = copy(v)
        new[k] = v
    return new

class BaseMigrator:
    """Migrates an object to the new type

    The base class has the following attributes:
    
     * fromType
       The portal type name the migration is migrating *from*
     * toType
       The portal type name the migration is migrating *to*
     * map
       A dict which maps old attributes/function names to new
     * subtransaction
       Commit a subtransaction after X migrations
     * old
       The old object which has to be migrated
     * new
       The new object created by the migration 
     * parent
       The folder where the old objects lives
     * orig_id
       The id of the old objet before migration
     * old_id
       The id of the old object while migrating
     * new_id
       The id of the new object while and after the migration
     * kwargs
       A dict of additional keyword arguments applied to the migrator  
    """
    fromType = ''
    toType   = ''
    map      = {}

    subtransaction = 100

    def __init__(self, obj, **kwargs):
        self.old = aq_inner(obj)
        self.orig_id = self.old.getId()
        self.old_id = '%s_MIGRATION_' % self.orig_id
        self.new = None
        self.new_id = self.orig_id
        self.parent = aq_parent(self.old)
        self.kwargs = kwargs

        # safe id generation
        while hasattr(aq_base(self.parent), self.old_id):
            self.old_id+='X'

    def getMigrationMethods(self):
        """Calculates a nested list of callables used to migrate the old object
        """
        beforeChange = []
        methods      = []
        lastmethods  = []
        for name in dir(self):
            if name.startswith('beforeChange_'):
                method = getattr(self, name)
                if callable(method):
                    beforeChange.append(method)
            if name.startswith('migrate_'):
                method = getattr(self, name)
                if callable(method):
                    methods.append(method)
            if name.startswith('last_migrate_'):
                method = getattr(self, name)
                if callable(method):
                    lastmethods.append(method)

        afterChange = methods+[self.custom]+lastmethods
        return (beforeChange, afterChange, )

    def migrate(self, unittest=0):
        """Migrates the object
        """
        beforeChange, afterChange = self.getMigrationMethods()

        for method in beforeChange:
            __traceback_info__ = (self, method, self.old, self.orig_id)
            # may raise an exception, catch it later
            method()

        self.renameOld()
        self.createNew()

        for method in afterChange:
            __traceback_info__ = (self, method, self.old, self.orig_id)
            # may raise an exception, catch it later
            method()

        self.reorder()
        self.remove()

    __call__ = migrate

    def renameOld(self):
        """Renames the old object

        Must be implemented by the real Migrator
        """
        raise NotImplementedError

    def createNew(self):
        """Create the new object

        Must be implemented by the real Migrator
        """
        raise NotImplementedError

    def custom(self):
        """For custom migration
        """
        pass

    def migrate_properties(self):
        """Migrates zope properties

        Removes the old (if exists) and adds a new
        """
        if not hasattr(aq_base(self.old), 'propertyIds') or \
          not hasattr(aq_base(self.new), '_delProperty'):
            # no properties available
            return None

        for id in self.old.propertyIds():
            LOG("propertyid: " + str(id))
            if id in ('title', 'description'):
                # migrated by dc
                continue
            if id in ('content_type', ):
                # has to be taken care of separately
                LOG("property with id: %s not migrated" % str(id))
                continue
            value = self.old.getProperty(id)
            type = self.old.getPropertyType(id)
            LOG("value: " + str(value) + "; type: " + str(type))
            if self.new.hasProperty(id):
                self.new._delProperty(id)
            LOG("property: " + str(self.new.getProperty(id)))
            __traceback_info__ = (self.new, id, value, type)
             
            # continue if the object already has this attribute
            if getattr(aq_base(self.new), id, _marker) is not _marker:
                continue
             
            self.new.manage_addProperty(id, value, type)

    def migrate_owner(self):
        """Migrates the zope owner
        """
        # getWrappedOwner is not always available
        if hasattr(aq_base(self.old), 'getWrappedOwner'):
            owner = self.old.getWrappedOwner()
            self.new.changeOwnership(owner)
            LOG("changing owner via changeOwnership: %s" % str(self.old.getWrappedOwner()))
        else:
            # fallback
            # not very nice but at least it works
            # trying to get/set the owner via getOwner(), changeOwnership(...)
            # did not work, at least not with plone 1.x, at 1.0.1, zope 2.6.2
            LOG("changing owner via property _owner: %s" % str(self.old.getOwner(info = 1)))
            self.new._owner = self.old.getOwner(info = 1)

    def migrate_localroles(self):
        """Migrate local roles
        """
        self.new.__ac_local_roles__ = None
        # clean the auto-generated creators by Archetypes ExtensibleMeatadata
        self.new.setCreators([])
        local_roles = self.old.__ac_local_roles__
        if not local_roles:
            owner = self.old.getWrappedOwner()
            self.new.manage_setLocalRoles(owner.getId(), ['Owner'])
        else:
            self.new.__ac_local_roles__ = copy(local_roles)


    def migrate_withmap(self):
        """Migrates other attributes from obj.__dict__ using a map

        The map can contain both attribute names and method names

        'oldattr' : 'newattr'
            new.newattr = oldattr
        'oldattr' : ''
            new.oldattr = oldattr
        'oldmethod' : 'newattr'
            new.newattr = oldmethod()
        'oldattr' : 'newmethod'
            new.newmethod(oldatt)
        'oldmethod' : 'newmethod'
            new.newmethod(oldmethod())
        """
        for oldKey, newKey in self.map.items():
            LOG("oldKey: " + str(oldKey) + ", newKey: " + str(newKey))
            if not newKey:
                newKey = oldKey
            oldVal = getattr(self.old, oldKey)
            newVal = getattr(self.new, newKey)
            if callable(oldVal):
                value = oldVal()
            else:
                value = oldVal
            if callable(newVal):
                newVal(value)
            else:
                setattr(self.new, newKey, value)

    def remove(self):
        """Removes the old item

        Must be implemented by the real Migrator
        """
        raise NotImplementedError

    def reorder(self):
        """Reorder the new object in its parent

        Must be implemented by the real Migrator
        """
        raise NotImplementedError

class BaseCMFMigrator(BaseMigrator):
    """Base migrator for CMF objects
    """

    def migrate_dc(self):
        """Migrates dublin core metadata
        """
        # doesn't work!
        # shure? works for me
        for accessor, mutator in METADATA_MAPPING:
            oldAcc = getattr(self.old, accessor)
            newMut = getattr(self.new, mutator)
            #newAcc = getattr(self.new, accessor)
            oldValue = oldAcc()
            if accessor is 'Language' and not oldValue:
                # fix empty values in Language DC data set
                oldValue = self.kwargs.get('default_language', 'en')
            newMut(oldValue)

    def migrate_workflow(self):
        """migrate the workflow state
        """
        wfh = getattr(self.old, 'workflow_history', None)
        if wfh:
            wfh = copyPermMap(wfh)
            self.new.workflow_history = wfh

    def migrate_allowDiscussion(self):
        """migrate allow discussion bit
        """
        if getattr(aq_base(self.old), 'allowDiscussion', _marker) is not _marker and \
          getattr(aq_base(self.new), 'isDiscussable', _marker)  is not _marker:
            self.new.isDiscussable(self.old.allowDiscussion())

    def migrate_discussion(self):
        """migrate talkback discussion bit
        """
        talkback = getattr(self.old.aq_inner.aq_explicit, 'talkback', _marker)
        if talkback is _marker:
            return
        else:
            self.new.talkback = talkback

    def beforeChange_storeDates(self):
        """Safe creation date and modification date
        """
        self.old_creation_date = self.old.CreationDate()
        self.old_mod_date = self.old.ModificationDate()

    def last_migrate_date(self):
        """migrate creation / last modified date

        Must be called as *last* migration
        """
        self.new.creation_date = DateTime(self.old_creation_date)
        self.new.setModificationDate(DateTime(self.old_mod_date))

class ItemMigrationMixin:
    """Migrates a non folderish object
    """

    def renameOld(self):
        """Renames the old object
        """
        LOG("renameOld | orig_id: " + str(self.orig_id) + "; old_id: " + str(self.old_id))
        LOG(str(self.old.absolute_url()))
        unrestricted_rename(self.parent, self.orig_id, self.old_id)
        #self.parent.manage_renameObject(self.orig_id, self.old_id)

    def createNew(self):
        """Create the new object
        """
        _createObjectByType(self.toType, self.parent, self.new_id)
        self.new = getattr(aq_inner(self.parent).aq_explicit, self.new_id)

    def remove(self):
        """Removes the old item
        """
        if REMOVE_OLD:
            self.parent.manage_delObjects([self.old_id])

    def reorder(self):
        """Reorder the new object in its parent
        """
        if IOrderedContainer.isImplementedBy(self.parent):
            self.parent.moveObject(self.new_id,self.parent.getObjectPosition(self.old_id))

class FolderMigrationMixin(ItemMigrationMixin):
    """Migrates a folderish object
    """

    def migrate_children(self):
        """Copy childish objects from the old folder to the new one

        I don't know wether it works or fails due the ExtensionClass, ZODB and
        acquisition stuff of zope

        It seems to work for me very well :)
        """
        orderAble = IOrderedContainer.isImplementedBy(self.old)
        orderMap = {}

        # using objectIds() should be safe with BrokenObjects
        for id in self.old.objectIds():
            obj = getattr(self.old.aq_inner.aq_explicit, id)
            # XXX Fix broken object support. Maybe we are able to migrate them?
            if isinstance(obj, BrokenClass):
                log('WARNING: BrokenObject in %s' % \
                    self.old.absolute_url(1))
                continue
            
            if orderAble:
                orderMap[id] = self.old.getObjectPosition(id)
            self.new._setObject(id, aq_base(obj), set_owner=0)
        
        # reorder items
        if orderAble:
            for id, pos in orderMap.items():
                self.new.moveObjectToPosition(id, pos)

class CMFItemMigrator(ItemMigrationMixin, BaseCMFMigrator):
    """Migrator for items implementing the CMF API
    """

class CMFFolderMigrator(FolderMigrationMixin, BaseCMFMigrator):
    """Migrator from folderish items implementing the CMF API
    """
