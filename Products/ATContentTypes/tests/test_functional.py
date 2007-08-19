# -*- coding: UTF-8 -*-
"""
"""

from Testing import ZopeTestCase
from Products.ATContentTypes.tests.atcttestcase import ATCTFunctionalSiteTestCase 

FILES = [
    'webdav.txt', 'http_access.txt', 'reindex_sanity.txt'
]

from zope.testing import doctest
OPTIONFLAGS = (doctest.ELLIPSIS |
               doctest.NORMALIZE_WHITESPACE)

def test_suite():
    import unittest
    suite = unittest.TestSuite()
    from Testing.ZopeTestCase import FunctionalDocFileSuite as FileSuite
    for testfile in FILES:
        suite.addTest(FileSuite(testfile,
                                optionflags=OPTIONFLAGS,
                                package="Products.ATContentTypes.tests",
                                test_class=ATCTFunctionalSiteTestCase)
                     )
    return suite
