# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import os
import sys
import jinja2

from buildbot.test.fake import fakemaster
from buildbot.util import in_reactor
from buildbot.util import json
from twisted.internet import defer
from buildbot.www.config import IndexResource
from buildbot.plugins.db import get_plugins


@in_reactor
@defer.inlineCallbacks
def processwwwindex(config):
    master = yield fakemaster.make_master()
    if not config.get('index-file'):
        print "Path to the index.html file is required with option --index-file or -i"
        defer.returnValue(1)
    path = config.get('index-file')
    if not os.path.isfile(path):
        print "Invalid path to index.html"
        defer.returnValue(2)
    plugins = get_plugins('www', None, load_now=False)
    plugins = dict((k, {}) for k in plugins.names if k != "base")

    fakeconfig = {"user": {"anonymous": True}}
    fakeconfig['buildbotURL'] = master.config.buildbotURL
    fakeconfig['title'] = master.config.title
    fakeconfig['titleURL'] = master.config.titleURL
    fakeconfig['multiMaster'] = master.config.multiMaster
    fakeconfig['versions'] = IndexResource.getEnvironmentVersions()
    fakeconfig['plugins'] = plugins
    outputstr = ''
    with open(path) as indexfile:
        template = jinja2.Template(indexfile.read())
        outputstr = template.render(configjson=json.dumps(fakeconfig))
    with open(path, 'w') as indexfile:
        indexfile.write(outputstr)
    defer.returnValue(0)
