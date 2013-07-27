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
import pwd
import pyquery
from multiprocessing.managers import BaseManager, BaseProxy

class DropParse():

    @property
    def files(self):
        return self._files

    def __init__(self):
        self._files = {}
        self.dirs = {}
        self.pq = None

    def parse(self, s):
        self.pq = pyquery.PyQuery(s)
        self.pq_listing = self.pq('ol.gallery-list-view')
        self.file_list = self.pq_listing.find('li.list-view-cols')
        for self.file in self.file_list:
            filename = self.getName()
            filesize = self.getSize()
            href = self.getHref()
            self._files[filename] = {'name': filename, 'size': filesize, 'href': href}
    def getName(self):
        self.pq_file = pyquery.PyQuery(self.file)
        return self.pq_file.find('a.filename-link').attr('href').split("/")[-1:][0]
    
    def getHref(self):
        self.pq_file = pyquery.PyQuery(self.file)
        return self.pq_file.find('a.filename-link').attr('href')

    def getSize(self):
        self.pq_file = pyquery.PyQuery(self.file)
        size = self.pq_file.find('div.filesize-col span.size').text()
        num, var = size.split(" ")
        if var.lower() == "mb": return int(float(num)*1024*1024)
        elif var.lower() == "kb": return int(float(num)*1024)
        else: return int(num)


class Cache(object):
    
    def __init__(self):
        self.cache = {}

    def loadCache(self, files):
        print 'loading cache'
        for fl in files:
            self.cache[fl] = {'data': urllib.urlopen(files[fl]['href'].replace("www.dropbox.com","dl-web.dropbox.com")).read()}
        return self.cache

class CacheManager(BaseManager):
    pass

CacheManager.register('Cache', Cache)

class DropFuse(Operations):

    def __init__(self, host, path=''):
        self.cache = None
        self.client = DropParse()
        self.client.url = host
        self.root = path
        f = \
            urllib.urlopen(host)
        s = f.read()
        self.now = time()
        self.client.parse(s)
        self.loadCache()
        

    def loadCache(self):
        self.cacheManager = CacheManager()
        self.cacheManager.start()
        cs = self.cacheManager.Cache()
        self.cache = cs.loadCache(self.client.files)


    def getattr(self, path, fh=None):
        uid = pwd.getpwuid(os.getuid()).pw_uid
        gid = pwd.getpwuid(os.getuid()).pw_gid
        now = time()
        
        for fl in self.client.files:
            if path == '/%s' % urllib.unquote(os.path.basename(fl)):
                return dict(
                    st_mode=S_IFREG | 0444,
                    st_size=self.client.files[fl]['size'],
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
            for fl in self.client.files:
                defaults.append(urllib.unquote(self.client.files[fl]['name']))

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
        for fl in self.client.files:
            if path == '/%s' % urllib.unquote(self.client.files[fl]['name']):
                return self.cache[fl]['data']


if __name__ == '__main__':
    if len(argv) != 3:
        print 'usage: %s <dropbox link> <mount point>' % argv[0]
        exit(1)
    
    link = argv[1]
    if re.match("#view:list$",link)==None:
        link = "%s#view:list"%link
   
    dropfuse = FUSE(DropFuse(link, argv[2]), argv[2],
                    foreground=True, nothreads=True)
