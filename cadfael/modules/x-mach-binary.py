# coding: utf-8
# pylint: disable=W0621,C0103,R0903,C0326
from __future__ import unicode_literals, print_function

import ctypes
import sys
import subprocess
import xml.etree.ElementTree as ET
from macholib.MachO import MachO
from macholib.mach_o import uuid_command, symtab_command, dylib_command, MH_MAGIC_64, N_UNDF, segment_command, segment_command_64

from cadfael.core import signals


class nlist(ctypes.Structure):
    """32bit nlist structure"""
    _fields_ = (
        ('n_un', ctypes.c_uint32),
        ('n_type', ctypes.c_uint8),
        ('n_sect', ctypes.c_uint8),
        ('n_desc', ctypes.c_uint16),
        ('n_value', ctypes.c_uint32),
    )


class nlist_64(ctypes.Structure):
    """64bit nlist structure"""
    _fields_ = (
        ('n_un', ctypes.c_uint32),
        ('n_type', ctypes.c_uint8),
        ('n_sect', ctypes.c_uint8),
        ('n_desc', ctypes.c_uint16),
        ('n_value', ctypes.c_uint64),
    )


def parse_strings(text, strings, ucode):
    if len(text) > 0:
        code = 'utf-8' if ucode is False else 'utf-16'
        for s in text.decode(code, 'ignore').split('\0'):
            if len(s) > 0:
                strings.add(s)


def get_info(path):
    """extract symbol information from a macho file"""
    uuid = None
    strings = set()
    dylibs = set()

    local = set()
    undef = set()
    objc_methods = set()
    objc_classes = set()

    # __TEXT sections to parse for strings, params to parse_strings
    sections = {
        '__cstring': (strings, False),
        '__ustring': (strings, True),
        '__objc_methname': (objc_methods, False),
        '__objc_classname': (objc_classes, False),
    }
    macho = None
    try:
        macho = MachO(path)
        #print(path)
    except ValueError:
        pass # not a MachO file
    if macho is not None:
        # I hate this library, but am lothed to re-write it
        for h in macho.headers:
            for c in h.commands:
                if isinstance(c[1], uuid_command):
                    uuid = ''
                    for c in c[1].uuid:
                        uuid += '%02x' % (ord(c))
                elif isinstance(c[1], symtab_command):
                    symtab = c[1]
                    with open(path, 'rb') as f:
                        f.seek(h.offset + symtab.stroff)
                        string_table = f.read(symtab.strsize)

                        f.seek(h.offset + symtab.symoff)
                        for _ in range(0, symtab.nsyms):
                            if h.MH_MAGIC == MH_MAGIC_64:
                                nl = nlist_64()
                                f.readinto(nl)
                            else:
                                nl = nlist()
                                f.readinto(nl)
                            s = ''
                            for c in string_table[nl.n_un:]:
                                if ord(c) == 0:
                                    break
                                s += c
                            if nl.n_type & N_UNDF == N_UNDF:
                                # undefined - calls to func in other module
                                undef.add(s)
                            elif nl.n_type & N_UNDF != N_UNDF:
                                # symbol in n_sect; internal symbols
                                local.add(s)
                elif isinstance(c[1], dylib_command):
                    dylibs.add(str(c[2]).strip('\x00'))
                elif isinstance(c[1], segment_command) or isinstance(c[1], segment_command_64):
                    segname = c[1].segname.strip('\0')
                    if segname == '__TEXT':
                        for sec in c[2]:
                            secname = sec.sectname.strip('\0')
                            #print(segname, secname)
                            if secname in sections:
                                with open(path, 'rb') as f:
                                    f.seek(h.offset + sec.offset)
                                    text = f.read(sec.size)
                                parse_strings(text, *sections[secname])
    symbols = {
        'local': list(local),
        'undef': list(undef),
        'objc_methods': list(objc_methods),
        'objc_classes': list(objc_classes)
    }                                
    return uuid, symbols, strings, dylibs


def get_codesign(path):
    """get codesign info from the binary"""
    ident = None
    entitlements = None
    out = subprocess.check_output([
        'codesign', '-dvvv', '--entitlements', '-', path
    ], stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
        
    for line in out.split('\n'):
        #print(line)
        if line.startswith('Identifier'):
            _, ident = line.split('=')
    s = out.find('<?xml version="1.0" encoding="UTF-8"?>')
    if s != -1:
        entitlementsxml = out[s:]
        entitlements = obj_from_entitlements(entitlementsxml)
    return ident, entitlements


def obj_from_entitlements(entitlementsxml):
    """parse entitlements xml and produce a dict"""
    root = ET.fromstring(entitlementsxml)
    return parse_entitlement_dict(root.find('dict'))


def parse_entitlement_dict(el):
    retval = []
    key = None
    for child in el:
        if key is None:
            key = child.text
        else:
            # value
            value = None
            if child.tag == 'true':
                value = True
            elif child.tag == 'false':
                value = False
            elif child.tag == 'string':
                value = child.text
            elif child.tag == 'integer':
                value = int(child.text)
            elif child.tag == 'array':
                value = []
                for a in child:
                    value.append(a.text)
            elif child.tag == 'dict':
                value = parse_entitlement_dict(child)
            else:
                raise NotImplementedError('unexpected plist type: %s' % child.tag)
            retval.append({ 'name': key, 'value': value })
            key = None
    return retval


@signals.receiver(
    signals.inode,
    fmt='-',
    details__mime_type='application/x-mach-binary'
)
def signals_inode(inode, path):
    """extracts info from mach-o files"""
    #print(path)
    uuid, symbols, strings, dylibs = get_info(path)
    ident, entitlements = get_codesign(path)
    inode['details']['uuid'] = uuid
    inode['details']['symbols'] = symbols
    inode['details']['strings'] = list(strings)
    inode['details']['dylibs'] = list(dylibs)
    inode['details']['identifier'] = ident
    inode['details']['entitlements'] = entitlements


if __name__ == '__main__':
    uuid, local, undef, dylibs = get_info(sys.argv[1])
    for sym in list(local):
        print('T %s' % sym)
    print('T=%u' % len(local))
    for sym in list(undef):
        print('U %s' % sym)
    print('U=%u' % len(undef))
    for lib in list(dylibs):
        print('L %s' % lib)
    print('L=%u' % len(dylibs))
