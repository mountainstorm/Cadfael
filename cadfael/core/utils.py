# coding: utf-8
# pylint: disable=W0621,C0103,R0903,C0326
from __future__ import unicode_literals, print_function

from pymongo import MongoClient, ASCENDING

from cadfael.conf import settings


def create_volume(volname, delete_existing=True):
    """create a volume in the DB, clearing previous entries"""
    if delete_existing:
        # delete the old records in this volume
        db = settings.DB
        db.inodes.delete_many({ 'dev': volname })

    # now create it and setup indexes
    db.inodes.create_index([('dev', ASCENDING)])
    db.inodes.create_index([('chmod', ASCENDING)])
    db.inodes.create_index([('paths', ASCENDING)])


def fork():
    """helper function to recreate DB connection in a child"""
    db = settings.DBADDR.split(':')
    db[1] = int(db[1])
    settings.DB = MongoClient(db[0], db[1]).cadfael
