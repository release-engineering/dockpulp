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

import dockpulp

log = dockpulp.log

def get_opts():
    usage="""%prog [options] environment
create the everything repository in the given environment"""
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--debug', default=False, action='store_true',
        help='turn on debugging output')
    parser.add_option('-p', '--password', help='specify the account password')
    parser.add_option('-u', '--username', default='admin',
        help='provide an account besides "admin"')
    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.error('You must provide an environment to create the repository')
    return opts, args

def create_everything(dpo):
    """create the everything repo with the given dockpulp object"""
    dpo.createRepo(dockpulp.HIDDEN,
        '/content/this/does/not/matter',
        desc='hidden repository for RCM use that contains everything',
        title='RCM Hidden repository',
        distributors=False)
    # remove distributors from the hidden repository so it is never published

if __name__ == '__main__':
    opts, args = get_opts()
    p = dockpulp.Pulp(env=args[0])
    p.login(opts.username, opts.password)
    if opts.debug:
        p.setDebug()
    create_everything(p)
