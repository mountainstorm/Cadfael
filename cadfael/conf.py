# coding: utf-8
# pylint: disable=W0621,C0103,R0903
from __future__ import unicode_literals, print_function

import imp
import argparse
from pymongo import MongoClient

import cadfael.core.settings
import cadfael.core.signals


class Settings(object):
    """Settings object, holds all the settings"""

    def __init__(self):
        """Creates object and loads all the default settings"""
        self.update(cadfael.core.settings)

    def update(self, module):
        """updates settings with those from module"""
        for item in dir(module):
            if item.isupper():
                setattr(self, item, getattr(module, item))

settings = Settings()


def argument_parser(desc, banner=True):
    """create argment parser with global options"""
    parser = argparse.ArgumentParser(desc)
    parser.add_argument(
        '-q',
        dest='banner',
        default=banner,
        action='store_false',
        help='suppress printing banner'
    )
    parser.add_argument(
        '--db', dest='dbaddr', default=cadfael.core.settings.DBADDR,
        help='address of database e.g. %s' % cadfael.core.settings.DBADDR
    )
    parser.add_argument(
        '-s', '--settings', dest='settings', default=None,
        help='path to settings.py file to use'
    )
    cadfael.core.signals.register_args(parser)

    orig = parser.parse_args
    def parse():
        """wrapper for argparse parse"""
        args = orig() # call original parser

        # process any global settings
        if args.settings is not None:
            # load any override settings
            mod = imp.load_source(
                'cadfael.settings', args.settings
            )
            settings.update(mod)
        settings.DBADDR = args.dbaddr

        # load all the modules
        for mod in settings.MODULES:
            __import__(mod)

        # create the DB connection
        db = settings.DBADDR.split(':')
        db[1] = int(db[1])
        # connect=False because: http://api.mongodb.com/python/current/faq.html#multiprocessing
        settings.DB = MongoClient(db[0], db[1], connect=False).cadfael

        cadfael.core.signals.parse_args(args)
        # ready to run - print banner
        if args.banner is True:
            print('''
              # ###                  ##       /##               ###     
            /  /###  /                ##    #/ ###               ###    
           /  /  ###/                 ##   ##   ###               ##    
          /  ##   ##                  ##   ##                     ##    
         /  ###                       ##   ##                     ##    
        ##   ##          /###     ### ##   ###### /###     /##    ##    
        ##   ##         / ###  / ######### ##### / ###  / / ###   ##    
        ##   ##        /   ###/ ##   ####  ##   /   ###/ /   ###  ##    
        ##   ##       ##    ##  ##    ##   ##  ##    ## ##    ### ##    
        ##   ##       ##    ##  ##    ##   ##  ##    ## ########  ##    
         ##  ##       ##    ##  ##    ##   ##  ##    ## #######   ##    
          ## #      / ##    ##  ##    ##   ##  ##    ## ##        ##    
           ###     /  ##    /#  ##    /#   ##  ##    /# ####    / ##    
            ######/    ####/ ##  ####/     ##   ####/ ## ######/  ### / 
              ###       ###   ##  ###       ##   ###   ## #####    ##/  
   
------------------- https://github.com/mountainstorm/cadfael -------------------
'''.encode('utf-8'))
        return args
    parser.parse_args = parse
    return parser

