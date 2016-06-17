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

from contextlib import closing
from optparse import OptionParser
import os
import requests
import shutil
import sys
import logging
import ast
import subprocess

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

silent = logging.StreamHandler(sys.stdout)
silformatter = logging.Formatter("")
silent.setFormatter(silformatter)

def main():
    usage = """CLI for Pulp instances providing Docker content

%prog [options] directive [directive-options]"""
    parser = OptionParser(usage=usage)
    parser.disable_interspersed_args()
    parser.add_option('-C', '--cert', default=False,
        help='specify a certificate file, use with -K')
    parser.add_option('-K', '--key', default=False,
        help='specify a key file, use with -C')
    parser.add_option('-d', '--debug', default=False, action='store_true')
    parser.add_option('-s', '--server', default='qa',
        help='a Pulp environment to execute against')
    parser.add_option('-c', '--config-file',
        default=dockpulp.DEFAULT_CONFIG_FILE,
        help='config file to use [default: %default]')
    opts, args = parser.parse_args()
    cmd = find_directive('do_', args)
    try:
        cmd(opts, args[1:])
    except dockpulp.errors.DockPulpConfigError, pe:
        log.error('Configuration error: %s' % str(pe))
        log.error('')
        log.error('Something is wrong in /etc/dockpulp.conf, or you')
        log.error('mistyped an option you are passing to --server')
        sys.exit(1)
    except dockpulp.errors.DockPulpInternalError, pe:
        log.error('Internal failure: %s' % str(pe))
        sys.exit(1)
    except dockpulp.errors.DockPulpLoginError, pe:
        log.error('Login Error: %s' % str(pe))
        log.error(
            'Did you log into the %s environment with the right password?' %
            opts.server)
        sys.exit(1)
    except dockpulp.errors.DockPulpServerError, pe:
        log.error('Server-side problem: %s' % str(pe))
        log.error('')
        log.error('The only recourse here is to contact IT. :(')
        sys.exit(1)
    except dockpulp.errors.DockPulpTaskError, pe:
        log.error('Subtask failed: %s' % pe)
        log.error('')
        log.error('Use the "task" command to see the full traceback')
        log.error('Use --debug to see inspect the server request')
        sys.exit(1)
    except dockpulp.errors.DockPulpError, pe:
        log.error('Error: %s' % str(pe))
        log.error('')
        log.error('For help diagnosing errors, go to the link below. The API')
        log.error('we used is shown above with the HTTP response code.')
        log.error('   http://pulp-dev-guide.readthedocs.org/en/latest/integration/index.html')
        sys.exit(1)

def pulp_login(bopts):
    p = dockpulp.Pulp(env=bopts.server, config_file=bopts.config_file)
    if bopts.debug:
        p.setDebug()
    if bopts.cert:
        p.certificate = bopts.cert
    if bopts.key:
        p.key = bopts.key

    default_creddir = os.path.expanduser('~/.pulp')
    if (not p.certificate or not p.key) and\
        (not os.path.exists(os.path.join(default_creddir, p.AUTH_CER_FILE)) or\
         not os.path.exists(os.path.join(default_creddir, p.AUTH_KEY_FILE))):
        log.error('You need to log in with a user/password first.')
        sys.exit(1)
    else:
        creddir = os.path.expanduser('~/.pulp')
        p.set_certs(os.path.join(creddir,  p.AUTH_CER_FILE),
                    os.path.join(creddir, p.AUTH_KEY_FILE))
    return p

def list_directives(prefix):
    """list all base directives supported by relengo-tool"""
    dirs = [(k.replace(prefix, ''), v.__doc__)
        for k, v in globals().items() if k.startswith(prefix)]
    dirs.sort()
    for directive in dirs:
        print '  %s: %s' % (directive)
    sys.exit(2)

def find_directive(prefix, arguments):
    """
    From a prefix and directive on the cli, find the function we want to call
    and return it. If we can't find it or one wasn't specified, print out what
    is available and exit.
    """
    if len(arguments) > 0:
        cmd = globals().get(prefix + arguments[0], None)
        if cmd == None:
            log.error('Unknown directive: %s' % arguments[0])
        else:
            return cmd
    print 'Available directives:\n'
    list_directives(prefix)

def get_bool_from_string(string):
    """
    Return bool based on string
    """
    if isinstance(string, bool):
        return string
    if string.lower() in ['t', 'true']:
        return True
    if string.lower() in ['f', 'false']:
        return False
    log.error("Could not convert %s to bool" % string)
    log.error("Accepted strings are t, true, f, false")
    sys.exit(1)

def _test_repo(dpo, dockerid, redirect, pulp_imgs, protected=False, cert=None, key=None, silent=False):
    """confirm we can reach crane and get data back from it"""
    # manual: curl --insecure https://registry.access.stage.redhat.com/v1/repositories/rhel6/rhel/images
    #         curl --insecure https://registry.access.stage.redhat.com/v1/repositories/rhel6.6/images
    result = {}
    result['error'] = False
    url = dpo.registry + '/v1/repositories/' + dockerid + '/images'
    log.info('  Testing Pulp and Crane data')
    log.debug('  contacting %s' % url)
    if protected:
        log.info('  Repo is protected, trying certs')
        answer = requests.get(url, verify=False)
        if answer.content != 'Not Found':
            log.warning('  Crane not reporting 404 - possibly unprotected?')
        if cert is None and key is None:
            log.error('  Must provide a cert to test protected repos, skipping')
            result['error'] = True
            return result

    try:
        answer = requests.get(url, verify=False, cert=(cert,key))
    except requests.exceptions.SSLError:
        log.error('  Request failed due to invalid cert or key')
        result['error'] = True
        return result


    log.debug('  crane content: %s' % answer.content)
    log.debug('  status code: %s' % answer.status_code)
    response = answer.content
    if response == 'Not Found':
        log.error('  Crane returned a 404')
        result['error'] = True
        return result

    try:
        j = json.loads(response)
    except ValueError, ve:
        log.error('  Crane did not return json')
        result['error'] = True
        return result
        
    p_imgs = set(pulp_imgs)
    c_imgs = set([i['id'] for i in j])

    pdiff = p_imgs - c_imgs
    cdiff = c_imgs - p_imgs
    pdiff = list(pdiff)
    pdiff.sort()
    cdiff = list(cdiff)
    cdiff.sort()
    result['in_pulp_not_crane'] = pdiff
    result['in_crane_not_pulp'] = cdiff


    log.debug('  crane images: %s' % c_imgs)
    log.debug('  pulp images: %s' % p_imgs)
    same = True
    for p_img in p_imgs:
        if p_img not in c_imgs:
            same = False
    for c_img in c_imgs:
        if c_img not in p_imgs:
            same = False
    if not same:
        pdiff = ', '.join((p_imgs - c_imgs))
        cdiff = ', '.join((c_imgs - p_imgs))
        
        log.error('  Pulp images and Crane images are not the same:')
        if len(pdiff) > 0:
            log.error('    In Pulp but not Crane: ' + pdiff)
        if len(cdiff) > 0:
            log.error('    In Crane but not Pulp: ' + cdiff)
        result['error'] = True
        return result
                    
    log.info('  Pulp and Crane data reconciled correctly, testing content')

    # Testing for redirect, only need to check one url per image
    if redirect:
        missing = set([])
        reachable = set([])
        for img in pulp_imgs:
            for ext in ('json', 'ancestry', 'layer'):
                url = redirect + '/' + img + '/' + ext
                log.debug('  reaching for %s' % url)
                try:
                    with closing(requests.get(url, verify=False, stream=True, cert=(cert,key))) as answer:
                        log.debug('    got back a %s' % answer.status_code)
                        if answer.status_code != 200:
                            missing.add(img)
                        else:
                            reachable.add(img)
                except requests.exceptions.SSLError:
                    log.error('  Request failed due to invalid cert or key')
                    result['error'] = True
                    return result

        missing = list(missing)
        missing.sort()
        reachable = list(reachable)
        reachable.sort()
        result['missing_layers'] = missing
        result['reachable_layers'] = reachable
        if len(missing) > 0:
            log.error('  Could not reach images:')
            log.error('    ' + ', '.join(missing))
            result['error'] = True
            return result

        log.info('  All images are reachable, testing Crane ancestry')

    # Testing for default pulp redirect, requires checking both v1 and v2 urls
    else:
        missingv1 = set([])
        missingv2 = set([])
        reachablev1 = set([])
        reachablev2 = set([])
        reponame = 'redhat-' + dockerid.replace('/', '-')
        if dpo.url[:5] == 'https':
            filerurl = dpo.url.replace('https', 'http', 1)

        for img in pulp_imgs:
            for ext in ('json', 'ancestry', 'layer'):
                urlv1 = filerurl + '/pulp/docker/v1/' + reponame + '/' + img + '/' + ext
                urlv2 = filerurl + '/pulp/docker/v2/' + reponame + '/' + img + '/' + ext

                log.debug('  reaching for %s' % urlv1)

                try:
                    with closing(requests.get(urlv1, verify=False, stream=True, cert=(cert,key))) as answer:
                        log.debug('    got back a %s' % answer.status_code)
                        if answer.status_code != 200:
                            missingv1.add(img)
                        else:
                            reachablev1.add(img)
                except requests.exceptions.SSLError:
                    log.error('  Request failed due to invalid cert or key')
                    result['error'] = True
                    return result

                log.debug('  reaching for %s' % urlv2)

                try:
                    with closing(requests.get(urlv2, verify=False, stream=True, cert=(cert,key))) as answer:
                        log.debug('    got back a %s' % answer.status_code)
                        if answer.status_code != 200:
                            missingv2.add(img)
                        else:
                            reachablev2.add(img)
                except requests.exceptions.SSLError:
                    log.error('  Request failed due to invalid cert or key')
                    result['error'] = True
                    return result

        missingv1 = list(missingv1)
        missingv1.sort()
        reachablev1 = list(reachablev1)
        reachablev1.sort()
        result['missing_layers_v1'] = missingv1
        result['reachable_layers_v1'] = reachablev1
        missingv2 = list(missingv2)
        missingv2.sort()
        reachablev2 = list(reachablev2)
        reachablev2.sort()
        result['missing_layers_v2'] = missingv2
        result['reachable_layers_v2'] = reachablev2

        if len(missingv1) > 0 and len(missingv2) > 0:
            log.error('  Could not reach v1 or v2 images:')
            log.error('    ' + 'v1:' + ', '.join(missingv1))
            log.error('    ' + 'v2:' + ', '.join(missingv2))
            result['error'] = True
            return result
        elif len(missingv1) > 0:
            log.info('  v2 images are reachable, tests pass.')
            log.error('  Could not reach v1 images:')
            log.error('    ' + ', '.join(missingv1))
            result['error'] = True
            return result
        elif len(missingv2) > 0:
            log.info('  v1 images are reachable, tests pass.')
            log.error('  Could not reach v2 images:')
            log.error('    ' + ', '.join(missingv2))
            result['error'] = True
            return result
        
        log.info('  All images are reachable, testing Crane ancestry')

    # Testing all parent images in Crane. If one is down, docker pull will fail
    craneimages = list(c_imgs)
    parents = []
    for img in craneimages:
        url = dpo.registry + '/v1/images/' + img + '/json'
        log.debug('  reaching for %s' % url)
        try:
            answer = requests.get(url, verify=False, cert=(cert,key))
        except requests.exceptions.SSLError:
            log.error('  Request failed due to invalid cert or key')
            result['error'] = True
            return result

        log.debug('  crane content: %s' % answer.content)
        log.debug('  status code: %s' % answer.status_code)
        response = answer.content
        if response == 'Not Found':
            log.error('  Crane returned a 404')
            result['error'] = True
            if silent:
                continue
            return result
        try:
            j = json.loads(response)
        except ValueError, ve:
            log.error('  Crane did not return json')
            result['error'] = True
            if silent:
                continue
            return result

        try:
            parents.append(j['parent'])
        except KeyError:
            log.debug('  Image has no parent: %s' % img)

    while parents:
        missing = set([])
        imgs = parents
        parents = []
        for img in imgs:
            url = dpo.registry + '/v1/images/' + img + '/json'
            log.debug('  reaching for %s' % url)
            try:
                answer = requests.get(url, verify=False, cert=(cert,key))
            except requests.exceptions.SSLError:
                log.error('  Request failed due to invalid cert or key')
                result['error'] = True
                return result

            log.debug('  crane content: %s' % answer.content)
            log.debug('  status code: %s' % answer.status_code)
            response = answer.content
            if response == 'Not Found':
                log.error('  Crane returned a 404 on parent image %s' % img)
                result['error'] = True
                if silent:
                    missing.add(img)
                    continue
                return result
            try:
                j = json.loads(response)
            except ValueError, ve:
                log.error('  Crane did not return json on parent image %s' % img)
                result['error'] = True
                if silent:
                    continue
                return result
                
            try:
                parents.append(j['parent'])
            except KeyError:
                log.debug('  Image has no parent: %s' % img)
    
    log.info('  All ancestors reachable, tests pass')
    missing = list(missing)
    missing.sort()
    result['missing_ancestor_layers'] = missing
    return result

# all DO commands follow this line in alphabetical order

def do_ancestry(bopts, bargs):
    """
    dock-pulp ancestry [options] image-id
    List all layers associated with an image"""
    parser = OptionParser(usage=do_ancestry.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) != 1:
        parser.error('You must provide an image ID')
    p = pulp_login(bopts)
    ancestors = p.getAncestors(args[0])
    log.info('getting ancestors, listing the most recent first')
    for ancestor in ancestors:
        log.info(ancestor)

def do_associate(bopts, bargs):
    """
    dock-pulp associate [options] distributor-id repo-id
    Associate a distributor with a repo"""
    parser = OptionParser(usage=do_associate.__doc__)
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if len(args) != 2:
        parser.error('You must provide the distributor name and repo id')
    result = p.associate(args[0], args[1])
    log.info("Created distributor: %s", result['id'])

def do_clone(bopts, bargs):
    """
    dock-pulp clone [options] repo-id new-product-line new-image-name
    dock-pulp clone [options] --library repo-id  new-image-name
    Clone a docker repo, bringing content along"""
    parser = OptionParser(usage=do_clone.__doc__)
    parser.add_option('-l', '--library', help='create a "library"-level repo',
        default=False, action='store_true')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    productid = None
    if opts.library:
        if len(args) != 2:
            parser.error('You need a source repo id and a name for a library-level repo')
        repoid = 'redhat-%s' % (args[1])
    else:
        if len(args) != 3:
            parser.error('You need a source repo id, a new product line (rhel6, openshift3, etc), and a new image name')
        repoid = 'redhat-%s-%s' % (args[1], args[2])
        productid = args[1]

    log.info('cloning %s repo to %s' % (args[0], repoid))
    oldinfo = p.listRepos(args[0], content=True)[0]
    newrepo = p.createRepo(repoid, oldinfo['redirect'],
                        desc=oldinfo['description'], title=oldinfo['title'], 
                           protected=get_bool_from_string(oldinfo['protected']), 
                           productline=productid)
    log.info('cloning content in %s to %s' % (args[0], repoid))
    if len(oldinfo['images']) > 0:
        for img in oldinfo['images'].keys():
            p.copy(repoid, img)
            tags = {'tag': '%s:%s' % (','.join(oldinfo['images'][img]), img)}
            p.updateRepo(repoid, tags)
    else:
        log.info('no content to copy in')
    log.info('cloning complete')

def do_confirm(bopts, bargs):
    """
    dock-pulp confirm [options] [repo-id...]
    Confirm all images are reachable. Accepts regex!"""
    parser = OptionParser(usage=do_confirm.__doc__)
    parser.add_option('-c', '--cert', action='store', help='A cert used to authenticate protected repositories')
    parser.add_option('-k', '--key', action='store', help='A key used to authenticate protected repositories')
    parser.add_option('-s', '--silent', action='store_true', default=False, help='Return confirm output in machine readable form')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    rids = None
    if opts.silent:
        log.removeHandler(sh)
        log.addHandler(dockpulp.NullHandler())

    if len(args) > 0:
        rids = []
        for arg in args:
            if '*' in arg or '?' in arg:
                results = p.searchRepos(arg)
                if len(results) == 0:
                    log.warning('Regex did not match anything')
                    return
                else:
                    rids.extend(results)
            else:
                rids.append(arg)
    repos = p.listRepos(repos=rids, content=True)
    errors = 0
    repoids = {}
    for repo in repos:
        log.info('Testing %s' % repo['id'])
        imgs = repo['images'].keys()
        response = _test_repo(p, repo['docker-id'], repo['redirect'], imgs, repo['protected'], opts.cert, opts.key, opts.silent)
        if opts.silent:
            repoids[repo['id']] = response
        elif response['error']:
            errors += 1

    log.info('Testing complete... %s error(s)' % errors)

    if opts.silent:
        log.addHandler(silent)
        log.info(repoids)
    
    if errors >= 1:
        sys.exit(1)

def do_copy(bopts, bargs):
    """
    dock-pulp copy [options] dest-repo-id image-id [image-id...]
    Copy an image from one repo to another"""
    # TODO: copy over ancestors too
    parser = OptionParser(usage=do_copy.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) < 2:
        parser.error('You must provide a destination repository and image-id')
    p = pulp_login(bopts)
    for img in args[1:]:
        p.copy(args[0], img)
        log.info('copying successful')

def do_create(bopts, bargs):
    """
    dock-pulp create [options] product-line image-name content-url
    dock-pulp create [options] --library image-name content-url
    Create a repository for docker images
    content-url is not required if redirect-url = no in /etc/dockpulp.conf"""
    parser = OptionParser(usage=do_create.__doc__)
    parser.add_option('-d', '--description', help='specify a repo description',
        default='No description')
    parser.add_option('-l', '--library', help='create a "library"-level repo',
        default=False, action='store_true')
    parser.add_option('-t', '--title', help='set the title for the repo')
    parser.add_option('-p', '--protected', help='set the protected bit to true for the repo',
        default=False, action='store_true')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    url = None
    productid = None
    if opts.library:
        if len(args) != 2 and p.isRedirect():
            parser.error('You need a name for a library-level repo and a content-url')
        elif ( len(args) != 1 and len(args) != 2 ) and not p.isRedirect():
            parser.error('You need a name for a library-level repo')
        repoid = 'redhat-%s' % (args[0])
        if len(args) == 2:
            url = args[1]
    else:
        if len(args) != 3 and p.isRedirect():
            parser.error('You need a product line (rhel6, openshift3, etc), image name and a content-url')
        elif ( len(args) != 2 and len(args) != 3 ) and not p.isRedirect():
            parser.error('You need a product line (rhel6, openshift3, etc) and image name')
        productid = args[0] 
        repoid = 'redhat-%s-%s' % (args[0], args[1])
        if len(args) == 3:
            url = args[2]

    if url:
        if not url.startswith('/content'):
            parser.error('the content-url needs to start with /content')

    p.createRepo(repoid, url, desc=opts.description, title=opts.title, protected=opts.protected, productline=productid)
    log.info('repository created')

def do_delete(bopts, bargs):
    """
    dock-pulp delete [options] repo-id [repo-id...]
    Delete a repository; this will not affect content in other repos"""
    parser = OptionParser(usage=do_delete.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) < 1:
        parser.error('You must provide a repository ID')
    p = pulp_login(bopts)
    for repo in args:
        repoinfo = p.listRepos(repo, content=True)[0]
        p.deleteRepo(repo)
        log.info('deleted %s' % repo)
        if len(repoinfo['images']) > 0:
            log.info('Layers removed:')
            for img in repoinfo['images'].keys():
                log.info('    %s', img)
            log.info('Layers still exist in redhat-everything')

def do_disassociate(bopts, bargs):
    """
    dock-pulp disassociate [options] distributor-id repo-id
    Disassociate a distributor from a repo"""
    parser = OptionParser(usage=do_disassociate.__doc__)
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if len(args) != 2:
        parser.error('You must provide the distributor name and repo id')
    p.disassociate(args[0], args[1])

def do_empty(bopts, bargs):
    """
    dock-pulp empty [options] repo-id [repo-id]
    Remove all contents in a repository"""
    parser = OptionParser(usage=do_delete.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) < 1:
        parser.error('You must provide a repository ID')
    p = pulp_login(bopts)
    for repo in args:
        repoinfo = p.listRepos(repo, content=True)[0]
        log.debug('repo details we check for images in:')
        log.debug(repoinfo)
        if len(repoinfo['images']) > 0:
            log.info('removing all images from %s' % repo)
            for img in repoinfo['images'].keys():
                p.remove(repo, img)
        else:
            log.info('no images to remove')
        log.info('%s emptied' % repo)

def do_imageids(bopts, bargs):
    """
    dock-pulp imageids [options] image-id
    List all layers existing on server"""
    parser = OptionParser(usage=do_imageids.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) == 0:
        parser.error('You must provide an image ID(s)')
    p = pulp_login(bopts)
    result = p.getImageIdsExist(args)
    log.info(result)

def do_list(bopts, bargs):
    """
    dock-pulp list [options] [repo-id...]
    List one or more repositories. Accepts regex!"""
    parser = OptionParser(usage=do_list.__doc__)
    parser.add_option('-c', '--content', default=False, action='store_true',
        help='also return information about images in a repository')
    parser.add_option('-d', '--details', default=False, action='store_true',
        help='show details (not content) about each repository')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if len(args) == 0:
        repos = p.listRepos(content=opts.content)
    else:
        rids = []
        for arg in args:
            if '*' in arg or '?' in arg:
                results = p.searchRepos(arg)
                if len(results) == 0:
                    log.warning('Regex did not match anything')
                    return
                else:
                    rids.extend(results)
            else:
                rids.append(arg)
        repos = p.listRepos(repos=rids, content=opts.content)
    for repo in repos:
        log.info(repo['id'])
        if opts.details or opts.content:
            log.info('-' * len(repo['id']))
        if opts.details:
            for k, v in repo.items():
                if k in ('id', 'images'):
                    continue
                else:
                    log.info('%s = %s' % (k, v))
        if opts.content:
            log.info('v1 image details:')
            if len(repo['images'].keys()) == 0:
                log.info('  No images')
            else:
                imgs = repo['images'].keys()
                imgs.sort()
                for img in imgs:
                    log.info('  %s (tags: %s)' %
                        (img, ', '.join(repo['images'][img])))
                #for id, tags in repo['images'].items():
                #    log.info('  %s (tags: %s)' % (id, ', '.join(tags)))
            log.info('')
            log.info('v2 manifest details:')
            if len(repo['manifests'].keys()) == 0:
                log.info('  No manifests')
            else:
                manifests = repo['manifests'].keys()
                manifests.sort()
                output = {}
                for manifest in manifests:
                    layer = tuple(repo['manifests'][manifest]['layers'])

                    try: 
                        output[layer]
                    except KeyError:
                        output[layer] = {}

                    output[layer][manifest] = repo['manifests'][manifest]['tag']
                    
                images = output.keys()
                for image in images:
                    log.info('')
                    manifests = output[image].keys()
                    for manifest in manifests:
                        log.info('  Digest: %s  Tag: %s' %
                            (manifest, output[image][manifest]))
                    log.info('    Layers: ')
                    for layer in image:
                        log.info('      %s' % layer)
        if opts.details or opts.content:
            log.info('')

def do_login(bopts, bargs):
    """
    dock-pulp login [options]
    Login into pulp and get a session certificate"""
    parser = OptionParser(usage=do_login.__doc__)
    parser.add_option('-p', '--password', help='specify an account password')
    parser.add_option('-u', '--username', default='admin', help='pick username')
    opts, args = parser.parse_args(bargs)
    if not opts.password:
        parser.error('You should provide a password too')
    p = dockpulp.Pulp(env=bopts.server, config_file=bopts.config_file)
    p.login(opts.username, opts.password)
    creddir = os.path.expanduser('~/.pulp')
    if not os.path.exists(creddir):
        os.makedirs(creddir)
    shutil.copy(p.certificate, creddir)
    shutil.copy(p.key, creddir)
    log.info('Credentials stored in %s.' % creddir)
    log.info('You may run commands without a user/password now.')

def do_json(bopts, bargs):
    """
    dock-pulp json [options] [2> file.json]
    Dump the Pulp configuration in an environment in a json format"""
    parser = OptionParser(usage=do_json.__doc__)
    parser.add_option('-p', '--pretty', default=False, action='store_true',
        help='format the json into something human-readable')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    j = p.dump(pretty=opts.pretty)
    log.info('json dump follows this line on stderr')
    print >> sys.stderr, j

def do_release(bopts, bargs):
    """
    dock-pulp release [options] [repo-id...]
    Publish pulp configurations to Crane, making them live. Accepts regex!"""
    parser = OptionParser(usage=do_release.__doc__)
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if p.env == 'prod':
        log.warning('Releasing to production! Customers will see this!')
    if len(args) == 0:
        p.crane()
    else:
        rids = []
        for arg in args:
            if '*' in arg or '?' in arg:
                results = p.searchRepos(arg)
                if len(results) == 0:
                    log.warning('Regex did not match anything')
                    return
                else:
                    rids.extend(results)
            else:
                rids.append(arg)
        p.crane(repos=rids)
    log.info('pulp configuration(s) successfully exported')

def do_remove(bopts, bargs):
    """
    dock-pulp remove [options] repo-id image-id [image-id...]
    dock-pulp remove --list-orphans [--remove]
    Remove an image from a repo, or clean up orphaned content"""
    # TODO: figure out how to remove unneeded layers too
    parser = OptionParser(usage=do_remove.__doc__)
    parser.add_option('-l', '--list-orphans', default=False,
        action='store_true', help='list orphaned images')
    parser.add_option('-r', '--remove', default=False, action='store_true',
        help='Remove all orphaned content. USE WITH CAUTION')
    opts, args = parser.parse_args(bargs)
    if opts.list_orphans:
        p = pulp_login(bopts)
        orphans = p.listOrphans()
        log.info('Orphan docker images:')
        if len(orphans) == 0:
            log.info('  No orphans found')
        for orphan in orphans:
            log.info('  ' + orphan['image_id'])
        if opts.remove:
            log.info('removing all orphaned docker images')
            p.cleanOrphans()
            log.info('Orphaned docker images removed')
        sys.exit(0)
    if len(args) < 2:
        parser.error('You must provide a repo and image-id')
    p = pulp_login(bopts)
    images = p.listRepos(repos=args[0], content=True)[0]['images']
    for img in args[1:]:
        p.remove(args[0], img)
    log.info('calculating unneeded layers')
    images = p.listRepos(repos=args[0], content=True)[0]['images']
    tagged_images = set([i for i in images.keys() if len(images[i]) > 0])
    if len(tagged_images) == 0:
        log.info('No tagged images, no unneeded layers')
        sys.exit(0)
    ancestors = set()
    log.debug('tagged images: %s' % tagged_images)
    for tagged_image in tagged_images:
        ancestors.update(set(p.getAncestors(tagged_image)))
    log.debug('ancestors of tagged images: %s' % ancestors)
    unneeded = set(images.keys()) - ancestors - tagged_images
    log.debug('removing: %s' % unneeded)
    for img in unneeded:
        p.remove(args[0], img)
    log.info('removed images and unneeded layers')

def do_sync(bopts, bargs):
    """                                                                          
    dock-pulp sync [options] <env to sync from> repo-id
    Sync a repo from one environment to another"""
    parser = OptionParser(usage=do_sync.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) < 2:
        parser.error('You must provide an environment to sync from and a repo id')
    p = pulp_login(bopts)
    env = args[0]
    repo = args[1]

    repoinfo = p.syncRepo(env, repo, bopts.config_file)
    repoinfo = repoinfo[0]

    if len(repoinfo['images'].keys()) == 0:
        oldimgs = []
    else:
        oldimgs = repoinfo['images'].keys() 

    repoinfo = p.listRepos(repo, True)
    repoinfo = repoinfo[0]
    newimgs = repoinfo['images'].keys()
    imgs = list(set(newimgs) - set(oldimgs))
    imgs.sort()

    log.info(repoinfo['id'])
    log.info('-' * len(repoinfo['id']))    
    log.info('synced images:')

    if len(imgs) == 0:
        log.info('  No new images')
    else:
        for img in imgs:
            log.info(img)
        for img in imgs:
            p.copy('redhat-everything', img, repo)
    log.info('') 

def do_tag(bopts, bargs):
    """
    dock-pulp tag [options] repo-id image-id tags,with,commas
    dock-pulp tag [options] --remove repo-id image-id
    Tag an image with a tag in a repo"""
    parser = OptionParser(usage=do_tag.__doc__)
    parser.add_option('-r', '--remove', action='store_true', default=False,
        help='remove any tags associated with the image instead')
    opts, args = parser.parse_args(bargs)
    if opts.remove and len(args) != 2:
        parser.error(
            'You must provide a repo and image-id with --remove')
    elif not opts.remove and len(args) != 3:
        parser.error(
            'You must provide a repo, image-id, and comma-separated tags')
    p = pulp_login(bopts)
    # check that the image exists in the repository
    repoinfo = p.listRepos(args[0], content=True)[0]
    if args[1] not in repoinfo['images']:
        log.error('%s does not exist in %s' % (args[1], args[0]))
        sys.exit(1)
    if opts.remove:
        update = {'tag': ':%s' % args[1]}
    else:
        update = {'tag': '%s:%s' % (args[2], args[1])}
    # tags are repository attributes
    p.updateRepo(args[0], update)
    log.info('tagging successful')

def do_task(bopts, bargs):
    """
    dock-pulp task [options] task-id [task-id...]
    Display information about a task in pulp"""
    parser = OptionParser(usage=do_task.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) < 1:
        parser.error('You must provide a task ID')
    p = pulp_login(bopts)
    for task in args:
        taskinfo = p.getTask(task)
        log.info(taskinfo['task_id'])
        log.info('-' * 36)
        for field in ('state', 'error', 'task_type', 'queue', 'start_time', 'finish_time', 'traceback'):
            if not taskinfo.has_key(field):
                continue
            log.info('%s = %s' % (field, taskinfo[field]))

def do_update(bopts, bargs):
    """
    dock-pulp update [options] repo-id [repo-id...]
    Update metadata for a docker image repository"""
    parser = OptionParser(usage=do_update.__doc__)
    parser.add_option('-d', '--description',
        help='update the description for this repository')
    parser.add_option('-i', '--dockerid',
        help='set the docker ID (name) for this repo')
    parser.add_option('-r', '--redirect', help='set the redirect URL')
    parser.add_option('-t', '--title', help='set the title (short desc)')
    parser.add_option('-p', '--protected', 
        help='set the protected bit. Accepts (t, true, True) for True, (f, false, False) for False')
    opts, args = parser.parse_args(bargs)
    if len(args) < 1:
        parser.error('You must specify a repo ID (not the docker name)')
    p = pulp_login(bopts)
    updates = {}
    if opts.description:
        updates['description'] = opts.description
    if opts.dockerid:
        updates['repo-registry-id'] = opts.dockerid
    if opts.redirect:
        updates['redirect-url'] = opts.redirect
    if opts.title:
        updates['display_name'] = opts.title
    if opts.protected:
        updates['protected'] = get_bool_from_string(opts.protected)
    for repo in args:
        p.updateRepo(repo, updates)
        log.info('repo successfully updated')

def do_upload(bopts, bargs):
    """
    dock-pulp upload image-path [repo-id...]
    dock-pulp upload --list-uploads [--delete]
    Upload an image to a pulp repository"""
    parser = OptionParser(usage=do_upload.__doc__)
    parser.add_option('-l', '--list-uploads', default=False, action='store_true',
        help='List all upload request IDs')
    parser.add_option('-r', '--remove', default=False, action='store_true',
        help='Delete all outstanding upload reuqests. USE WITH CAUTION!')
    opts, args = parser.parse_args(bargs)
    if opts.list_uploads:
        p = pulp_login(bopts)
        uploads = p.listUploadRequests()
        log.info('Upload requests:')
        if len(uploads) == 0:
            log.info('  No outstanding uploads found')
        for upload in uploads:
            log.info('  ' + upload)
        if opts.remove:
            log.info('deleting existing upload requests')
            p.cleanUploadRequests()
            log.info('upload requests cleaned up')
        sys.exit(0)
    if len(args) < 1:
        parser.error('You must provide an image to upload')
    if not os.path.exists(args[0]):
        parser.error('Could not find %s' % args[0])
    log.info('uploading %s' % args[0])
    log.info('Ensuring image conforms to Pulp requirements')
    # TODO: this gets read again during the upload
    manifest = dockpulp.imgutils.get_manifest(args[0])
    metadata = dockpulp.imgutils.get_metadata(args[0])
    newimgs = dockpulp.imgutils.get_metadata_pulp(metadata).keys()
    log.info('Layers in this tarball:')
    for img in newimgs:
        log.info('  %s' % img)
    vers = dockpulp.imgutils.get_versions(manifest)
    good = True
    for id, version in vers.items():
        minor = int(version[2:version.index('.', 2)])
        if version.startswith('0') and minor < 10:
            log.error('Ancient docker version detected in layer')
            log.error('  %s (%s)' % (id, version))
            good = False
    if not good:
        log.error('Layer(s) in the image were created with an unsupported')
        log.error('version of docker, you cannot upload this image. Dev')
        log.error('needs to rebuild it with only supported versions at every')
        log.error('layer.')
        sys.exit(1)
    r_chk = dockpulp.imgutils.check_repo(args[0])
    if r_chk == 1:
        log.error('Image is missing a "repositories" file in the root of the')
        log.error('tarball filesystem. Engineering needs to rebuild it with')
        log.error('exactly 1 repository defined.')
        sys.exit(2)
    elif r_chk == 2:
        log.error('Pulp demands exactly one repository defined in the')
        log.error('"repositories" file, Engineering needs to rebuild it with')
        log.error('exactly 1 repository defined.')
        sys.exit(3)
    elif r_chk == 3:
        log.error('The "repositories" file references images that are not a')
        log.error('part of the tarball itself. Uploading this will yield')
        log.error('inconsistent repository metadata, so it is forbidden.')
        log.error('Make sure Engineering saved it with "docker save id:TAG"')
        sys.exit(4)
    if args[0].endswith('.xz'):
        log.error('Pulp can only extract gzipped tarballs, not xz.')
        log.error('Decompress it with unxz and then recompress with gzip')
        log.error('and try again.')
        sys.exit(5)
    p = pulp_login(bopts)
    p.upload(args[0])
    if len(args) > 1:
        for repo in args[1:]:
            for img in newimgs:
                p.copy(repo, img)
    log.info('Upload complete')

if __name__ == '__main__':
    main()
