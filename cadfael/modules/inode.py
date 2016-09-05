# coding: utf-8
# pylint: disable=W0621,C0103,R0903,C0326
from __future__ import unicode_literals, print_function

import os
import signal
import stat
import hashlib
from datetime import datetime
import multiprocessing
import magic

import cadfael.core.signals
from cadfael.conf import settings
from cadfael.core.utils import fork


def import_tree(volume_name, top):
    """import all files rooted at top"""
    # we have to do this magic as otherwise we can't properly ctrl-c
    if top[-1] != os.path.sep:
        top += os.path.sep
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    pool = multiprocessing.Pool(initializer=fork)
    signal.signal(signal.SIGINT, original_sigint_handler)
    try:
        res = pool.map_async(get_inode, list_tree(volume_name, top))
        while True:
            try:
                out = res.get(60)
                break
            except multiprocessing.TimeoutError:
                pass # ignore and try again
        #print(len(out))
    except KeyboardInterrupt:
        pool.terminate()
    else:
        pool.close()
    pool.join()


def list_tree(volume_name, top):
    """Simplified version of os.walk"""
    # https://hg.python.org/cpython/file/29f0836c0456/Lib/os.py#l276
    try:
        names = os.listdir(top)
    except IOError:
        return

    for name in names:
        path = os.path.join(top, name)
        isdir = os.path.isdir(path)
        yield volume_name, top, path, isdir
        if isdir:
            for volume_name, _, path, isdir in list_tree(volume_name, path):
                yield volume_name, top, path, isdir


def get_inode(arg):
    """extract the info for an inode"""
    volume_name, top, path, isdir = arg
    db = settings.DB
    inode = None
    if isdir:
        try:
            inode = get_base_inode(volume_name, path)
            cadfael.core.signals.inode(inode, path)
            route = path[len(top)-1:]
            db.inodes.update_one(
                { '_id': inode['_id'] },
                {
                    '$setOnInsert': inode,
                    '$addToSet': { 'paths': route }
                },
                True
            )
        except IOError:
            pass # permission denied
    else:
        try:
            inode = get_base_inode(volume_name, path)
            fmt = inode['fmt']
            if fmt == 'l':
                # symlink
                inode['details'] = {
                    'readlink': os.readlink(path)
                }
            elif fmt in ('s', 'p'):
                # sock or pipe
                raise NotImplementedError('socket or pipe: %s' % fmt) # XXX
            elif fmt in ('c', 'b'):
                # device
                raise NotImplementedError('device: %s' % fmt) # XXX
            else:
                # file
                inode['details'] = {
                    'mime_type': magic.from_file(path, mime=True),
                    'sha256': sha256_file(path)
                }
            cadfael.core.signals.inode(inode, path)
            route = path[len(top)-1:]
            db.inodes.update_one(
                { '_id': inode['_id'] },
                {
                    '$setOnInsert': inode,
                    '$addToSet': { 'paths': route }
                },
                True
            )
        except IOError:
            pass # permission denied
    return inode


def sha256_file(path):
    """generate the sha256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        data = f.read(4096)
        while len(data) > 0:
            sha256.update(data)
            data = f.read(4096)
    return sha256.hexdigest()


def get_base_inode(volume_name, path):
    """generate and inode object for a path"""
    st_type = {
        stat.S_IFSOCK: 's',
        stat.S_IFLNK: 'l',
        stat.S_IFREG: '-',
        stat.S_IFBLK: 'b',
        stat.S_IFDIR: 'd',
        stat.S_IFCHR: 'c',
        stat.S_IFIFO: 'p'
    }

    st = os.lstat(path)
    tpe = st_type[stat.S_IFMT(st.st_mode)]
    return {
        '_id': '%s:%u' % (volume_name, st.st_ino),
        'dev': volume_name,
        'fmt': tpe,
        'uid': st.st_uid, # XXX: can I convert these to names
        'gid': st.st_gid, # XXX: can I convert these to names
        'size': st.st_size,
        'atime': datetime.utcfromtimestamp(st.st_atime),
        'mtime': datetime.utcfromtimestamp(st.st_mtime),
        'ctime': datetime.utcfromtimestamp(st.st_ctime),
        'chmod': get_chmod(tpe, stat.S_IMODE(st.st_mode)),
        'chflags': get_chflags(st.st_flags),
        'details': {}
    }


def get_chmod(tpe, mode):
    """generate ls -l style cmod string"""
    rusr = ['-', 'r'][mode & stat.S_IRUSR != 0]
    wusr = ['-', 'w'][mode & stat.S_IWUSR != 0]
    xusr = ['-', 'x'][mode & stat.S_IXUSR != 0]
    if mode & stat.S_ISUID:
        if mode & stat.S_IXUSR == 0:
            xusr = 'S' # - & suid
        else:
            xusr = 's' # x & suid
    rgrp = ['-', 'r'][mode & stat.S_IRGRP != 0]
    wgrp = ['-', 'w'][mode & stat.S_IWGRP != 0]
    xgrp = ['-', 'x'][mode & stat.S_IXGRP != 0]
    if mode & stat.S_ISGID:
        if mode & stat.S_IXGRP == 0:
            xusr = 'S' # - & gid
        else:
            xusr = 's' # x & gid
    roth = ['-', 'r'][mode & stat.S_IROTH != 0]
    woth = ['-', 'w'][mode & stat.S_IWOTH != 0]
    xoth = ['-', 'x'][mode & stat.S_IXOTH != 0]
    if mode & stat.S_ISVTX:
        if mode & stat.S_IXOTH == 0:
            xusr = 'T' # - & sticky
        else:
            xusr = 't' # x & sticky
    return '%s%s%s%s%s%s%s%s%s%s' % (
        tpe,
        rusr, wusr, xusr,
        rgrp, wgrp, xgrp,
        roth, woth, xoth
    )


def get_chflags(flags):
    """generate an array of chflag strings"""
    retval = []
    if flags & stat.SF_ARCHIVED != 0:
        retval.append('archived')
    if flags & stat.UF_OPAQUE != 0:
        retval.append('opaque')
    if flags & stat.UF_NODUMP != 0:
        retval.append('nodump')
    if flags & (stat.UF_APPEND | stat.SF_APPEND) != 0:
        retval.append('sappend')
    if flags & (stat.UF_IMMUTABLE | stat.SF_IMMUTABLE) != 0:
        retval.append('uappend')
    if flags & stat.UF_HIDDEN != 0:
        retval.append('hidden')
    return retval
