#!/usr/bin/env python
# This file is part of dockpulp.
#
# dockpulp is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# dockpulp is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dockpulp.  If not, see <http://www.gnu.org/licenses/>.

from optparse import OptionParser
import os.path
import sys
import logging

try:
    # Python 2.6 and earlier
    import simplejson as json
except ImportError:
    if sys.version_info[0] > 2 or sys.version_info[1] > 6:
        import json
    else:
        # json on python 2.6 does not behave like simplejson
        raise

import dockpulp

log = dockpulp.log
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(levelname)-9s %(message)s")
sh.setFormatter(formatter)
log.addHandler(sh)


def get_opts():
    usage = """%prog [options] environment config.json
Recreate hidden repo in a Pulp environment based on a json dump."""
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--debug', default=False, action='store_true',
                      help='turn on debugging output')
    parser.add_option('-t', '--test', default=False, action='store_true',
                      help='test via dry run, will print out what would happen')
    parser.add_option('-p', '--password', help='specify the account password')
    parser.add_option('-u', '--username', default='admin',
                      help='provide an account besides "admin"')
    opts, args = parser.parse_args()
    if len(args) != 2:
        parser.error('Please specify an environment to recreate the hidden repo and a json file')
    if not os.path.exists(args[1]):
        parser.error('Could not find %s' % args[1])
    if not opts.password:
        parser.error('please use --password')
    return opts, args


def recreate(dpo, jfile, test=False):
    """Recreate the hidden repo in the environment provided."""
    try:
        repos = json.load(open(jfile, 'r'))
    except ValueError, e:
        log.error('%s does not contain valid json' % jfile)
        die(e)
    # make sure the hidden repository is available
    try:
        p.listRepos(repos=dockpulp.HIDDEN, content=True)[0]
    except dockpulp.errors.DockPulpError, e:
        if '404' in str(e):
            log.error(
                '  This command expects the %s repository to be available' %
                dockpulp.HIDDEN)
            die('  Missing %s repository, please see dock-pulp-bootstrap' %
                dockpulp.HIDDEN)
        else:
            raise
    log.info('  %s is present' % dockpulp.HIDDEN)

    # start copy of all images to hidden repo
    for repo in repos:
        if repo['id'] == dockpulp.HIDDEN:
            continue
        if test:
            log.info('  Would have copied images from %s to hidden repo', repo['id'])
        else:
            p.copy_filters(dockpulp.HIDDEN, source=repo['id'], v2=False)

        # set default in case env has no v2 content
        repo.setdefault('manifests', {})

        if test:
            log.info('  Would have copied manifests from %s to hidden repo', repo['id'])
        else:
            p.copy_filters(dockpulp.HIDDEN, source=repo['id'], v1=False)

    log.info('Hidden repo recreated.')


def die(msg):
    log.error(msg)
    sys.exit(1)


if __name__ == '__main__':
    opts, args = get_opts()
    p = dockpulp.Pulp(env=args[0])
    p.login(opts.username, opts.password)
    if opts.debug:
        p.setDebug()
    todo = recreate(p, args[1], opts.test)
