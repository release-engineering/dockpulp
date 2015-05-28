#!/usr/bin/python -tt

from optparse import OptionParser
import os.path
import requests
import simplejson as json
import sys

import dockpulp

log = dockpulp.log

def get_opts():
    usage="""%prog [options] environment config.json
Restore configuration to a Pulp environment based on a json dump."""
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--debug', default=False, action='store_true',
        help='turn on debugging output')
    parser.add_option('-p', '--password', help='specify the account password')
    parser.add_option('-u', '--username', default='admin',
        help='provide an account besides "admin"')
    opts, args = parser.parse_args()
    if len(args) != 2:
        parser.error('Please specify an environment to restore and a json file')
    if not os.path.exists(args[1]):
        parser.error('Could not find %s' % args[1])
    if not opts.password:
        parser.error('please use --password')
    return opts, args

def precheck(dpo, jfile):
    """
    confirm the hidden repository is available and contains all needed images
    """
    log.info('performing pre-checks in (empty) %s environment' % dpo.env)
    try:
        repos = json.load(open(jfile, 'r'))
    except ValueError, e:
        log.error('%s does not contain valid json' % jfile)
        die(e)
    # make sure the hidden repository is available
    try:
        hidden = p.listRepos(repos=dockpulp.HIDDEN, content=True)[0]
    except dockpulp.errors.DockPulpError, e:
        if '404' in str(e):
            log.error(
                '  This command expects the %s repository to be available' % \
                dockpulp.HIDDEN)
            die('  Missing %s repository, please see dock-pulp-bootstrap' % \
                dockpulp.HIDDEN)
        else:
            raise
    log.info('  %s is present' % dockpulp.HIDDEN)
    # ensure it contains all images we need
    img_need = set()
    for repo in repos:
        for img in repo['images'].keys():
            img_need.add(img)
    img_have = set(hidden['images'].keys())
    ndiff = ', '.join((img_need - img_have))
    hdiff = ', '.join((img_have - img_need))
    if len(ndiff) > 0:
        die('  Missing necessary images: ' + ndiff)
    if len(hdiff) > 0:
        log.warning('  Found some unnecessary images: ' + hdiff)
        log.warning('  Proceeding anyway, this is not fatal')
    log.info('  %s has all of the images we need' % dockpulp.HIDDEN)
    # environment must be empty
    if len(p.getAllRepoIDs()) > 0:
        die('Environment is not clean! Repositories exist!')
    log.info('Environment looks clean, pre-check tests pass.')
    return repos

def restore(dpo, jdata):
    """
    Configure a pulp instance with the json data provided, which should be a
    dump of configuration data from another existing environment.
    """
    log.info('Beginning restoration!')
    for repo in jdata:
        url = dockpulp.split_content_url(repo['redirect'])[1]
        dpo.createRepo(repo['id'], url, desc=repo['description'],
            title=repo['title'])
        for img in repo['images'].keys():
            dpo.copy(repo['id'], img)
            tags = {'tag': '%s:%s' % (','.join(repo['images'][img]), img)}
            dpo.updateRepo(repo['id'], tags)
    log.info('Restoration complete! (%s repositories)' % len(jdata))
    dpo.crane()

def die(msg):
    log.error(msg)
    sys.exit(1)

if __name__ == '__main__':
    opts, args = get_opts()
    p = dockpulp.Pulp(env=args[0])
    p.login(opts.username, opts.password)
    if opts.debug:
        p.setDebug()
    todo = precheck(p, args[1])
    restore(p, todo)

