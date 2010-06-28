#!/usr/bin/python
# -*- coding: utf-8 -*-
# author: Arek Bochinski , 2010, DropFuse - a linked DropBox folder filesystem
# version: 0.1
#
#See license note in COPYING document that must accompany this software

#See CAPABILITIES for limitations of this software

from fuse import *
import urllib, sgmllib, re, os
from sys import argv, exit

from time import time
from stat import S_IFDIR, S_IFLNK, S_IFREG
from errno import ENOENT, EACCES


class DropParser(sgmllib.SGMLParser):

    '''A simple parser for linked Dropbox folders.'''
    in_list = False
    d = 0
    in_file_size = False
    in_modified = False
    in_list = False
    in_dir = False
    in_file = False
    cur_file = ''
    cur_dir = ''
    url = ''

    def parse(self, s):
        """Parse the given string 's'."""
        self.feed(s)
        self.close()
        self.in_list = False
        self.in_dir = False
        self.in_file = False
        self.in_file_size = False
        self.in_modified = False
        self.cur_file = ''
        self.cur_dir = ''
        self.url = ''

    def __init__(self, verbose=0):
        """Initialise an object, passing 'verbose' to the superclass."""
        sgmllib.SGMLParser.__init__(self, verbose)
        self.files = {}
        self.dirs = {}

    def handle_data(self, data):
        cldata = data.strip()

        if self.in_file_size:
            if len(cldata) > 0:
                self.in_file_size = False
                self.files[self.cur_file]['file_size'] = cldata
        elif self.in_modified:
            if len(cldata) > 0:
                self.in_modified = False
                self.files[self.cur_file]['modified'] = cldata

    def start_div(self, attributes):
        if self.in_file:
            for (name, value) in attributes:
                if name == 'class' and value == 'filesize':
                    self.in_file_size = True
                    self.in_modified = False
                elif name == 'class' and value == 'modified':
                    self.in_file_size = False
                    self.in_modified = True

        if self.in_list:
            self.d += 1
            return
        for (name, value) in attributes:
            if name == 'id' and value == 'list-browser':
                self.d += 1
                self.in_list = True

    def end_div(self):
        if self.in_list:
            self.d -= 1

        if self.d <= 0:
            self.in_list = False

    def start_a(self, attributes):
        """Process a hyperlink and its 'attributes'."""
        self.in_dir = False
        self.in_file = False

        for (name, value) in attributes:
            if name == 'href' and value != '#':
                if self.in_list:
                    if re.search('v=l$', value):
                        self.in_dir = True
                        self.in_file = False
                        self.dirs[value] = {'name': value}
                        self.cur_dir = value
                    else:
                        self.in_file = True
                        self.in_dir = False
                        self.files[value] = {'name': value}
                        self.cur_file = value

    def get_dirs(self):
        '''Return the list of dirs.'''
        return self.dirs

    def get_files(self):
        '''Return the list of files.'''
        return self.files


class DropFuse(Operations):

    def __init__(self, host, path=''):
        self.client = DropParser()
        self.client.url = host
        self.root = path
        f = \
            urllib.urlopen('https://www.dropbox.com/s/c6ecc2plwconh5x#view:list'
                           )
        s = f.read()
        self.now = time()
        self.client.parse(s)


    def getattr(self, path, fh=None):
        uid = pwd.getpwuid(os.getuid()).pw_uid
        gid = pwd.getpwuid(os.getuid()).pw_gid
        now = time()
        for dir in self.client.get_dirs():
            if path == '/%s' \
                % urllib.unquote(os.path.basename(dir).split('?')[0]):
                return dict(
                    st_mode=S_IFDIR | 0755,
                    st_ctime=now,
                    st_mtime=now,
                    st_atime=now,
                    st_nlink=2,
                    st_uid=uid,
                    st_gid=gid,
                    )
        for fl in self.client.get_files():
            if path == '/%s' % urllib.unquote(os.path.basename(fl)):
                return dict(
                    st_mode=S_IFREG | 0444,
                    st_size=int(self.client.get_files()[fl]['file_size'
                                ]),
                    st_ctime=self.now,
                    st_mtime=self.now,
                    st_atime=self.now,
                    st_nlink=1,
                    )
        if path == '/':
            return dict(st_mode=S_IFDIR | 0755, st_ctime=now,
                        st_mtime=now, st_atime=now, st_nlink=3)
        else:
            return dict(
                st_mode=S_IFREG | 0444,
                st_size=0,
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
                st_nlink=1,
                )

    def mkdir(self, path):
        pass

    def mknod(
        self,
        path,
        mode,
        dev,
        ):
        return 0

    def create(self, path, mode):
        return 0

    def open(self, path, flags):
        return 0

    def readdir(self, path, fh):
        defaults = ['.', '..']
        if path == '/':
            for fl in self.client.get_files():
                defaults.append(urllib.unquote(os.path.basename(fl)))

            for dir in self.client.get_dirs():
                defaults.append('%s/'
                                % urllib.unquote(os.path.basename(dir).split('?'
                                )[0]))

        return defaults

    def read(
        self,
        path,
        size,
        offset,
        fh,
        ):
        
        data = self.get_file(path)
        if data == None:
            return 0
        if offset + size > len(data):
            size = len(data) - offset

        return data[offset:offset + size]

    def get_file(self, path):
        for fl in self.client.get_files():
            if path == '/%s' % urllib.unquote(os.path.basename(fl)):
                url=fl.replace("www.dropbox.com","dl-web.dropbox.com")
                return urllib.urlopen(url).read()


if __name__ == '__main__':
    if len(argv) != 3:
        print 'usage: %s <dropbox link> <mount point>' % argv[0]
        exit(1)
    
    link = argv[1]
    if re.match("#view:list$",link)==None:
        link = "%s#view:list"%link
   
    dropfuse = FUSE(DropFuse(link, argv[2]), argv[2],
                    foreground=True, nothreads=True)
