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

from functools import wraps
from optparse import OptionParser
from textwrap import dedent

import os
import shutil
import sys
import logging
import json

import dockpulp

log = dockpulp.log
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(levelname)-9s %(message)s")
sh.setFormatter(formatter)
log.addHandler(sh)

silent = logging.StreamHandler(sys.stdout)
silformatter = logging.Formatter("")
silent.setFormatter(silformatter)


def main(args=None):
    usage = dedent("""\
    CLI for Pulp instances providing Docker content

    %prog [options] directive [directive-options]""")
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
    opts, args = parser.parse_args(args)
    cmd = find_directive('do_', args)
    try:
        cmd(opts, args[1:])
    except dockpulp.errors.DockPulpConfigError, pe:
        log.error('Configuration error: %s' % str(pe))
        log.error('')
        log.error('Something is wrong in /etc/dockpulp.conf, /etc/dockpulpdistributors.json,')
        log.error('or /etc/dockpulpdistributions.json')
        log.error('Or you mistyped an option you are passing to --server')
        sys.exit(1)
    except dockpulp.errors.DockPulpInternalError, pe:
        log.error('Internal failure: %s' % str(pe))
        sys.exit(1)
    except dockpulp.errors.DockPulpLoginError, pe:
        log.error('Login Error: %s' % str(pe))
        log.error('Did you log into the %s environment with the right password?' %
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
        (not os.path.exists(os.path.join(default_creddir, p.AUTH_CER_FILE)) or
         not os.path.exists(os.path.join(default_creddir, p.AUTH_KEY_FILE))):
        log.error('You need to log in with a user/password first.')
        sys.exit(1)
    else:
        creddir = os.path.expanduser('~/.pulp')
        p.set_certs(os.path.join(creddir, p.AUTH_CER_FILE),
                    os.path.join(creddir, p.AUTH_KEY_FILE))
    return p


def list_directives(prefix):
    """List all base directives supported by relengo-tool."""
    dirs = [(k.replace(prefix, ''), v.__doc__)
            for k, v in globals().items() if k.startswith(prefix)]
    dirs.sort()
    for directive in dirs:
        print '  %s: %s' % (directive)
    sys.exit(2)


def find_directive(prefix, arguments):
    """Find callable directive.

    From a prefix and directive on the cli, find the function we want to call
    and return it. If we can't find it or one wasn't specified, print out what
    is available and exit.
    """
    if len(arguments) > 0:
        cmd = globals().get(prefix + arguments[0], None)
        if cmd is None:
            log.error('Unknown directive: %s' % arguments[0])
        else:
            return cmd
    print 'Available directives:\n'
    list_directives(prefix)


def get_bool_from_string(string):
    """Return bool based on string."""
    if isinstance(string, bool):
        return string
    if string.lower() in ['t', 'true']:
        return True
    if string.lower() in ['f', 'false']:
        return False
    log.error("Could not convert %s to bool" % string)
    log.error("Accepted strings are t, true, f, false")
    sys.exit(1)


# all DO commands follow this line in alphabetical order


def make_parser(f):
    """Helper function for creating parser.

    A new OptionParser object will be created and passed
    to function as "parser" keyword argument.
    Docstring from function will be used to set the
    description (first line), and usage (remaining text).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        description, usage = [x.rstrip() for x in f.__doc__.split('\n', 1)]
        parser = OptionParser(description=description, usage=usage)
        kwargs['parser'] = parser
        return f(*args, **kwargs)
    return wrapper


@make_parser
def do_ancestry(bopts, bargs, parser):
    """List all layers associated with an image.

    dock-pulp ancestry [options] image-id
    """
    opts, args = parser.parse_args(bargs)
    if len(args) != 1:
        parser.error('You must provide an image ID')
    p = pulp_login(bopts)
    ancestors = p.getAncestors(args[0])
    log.info('getting ancestors, listing the most recent first')
    for ancestor in ancestors:
        log.info(ancestor)


@make_parser
def do_associate(bopts, bargs, parser):
    """Associate a distributor with a repo.

    dock-pulp associate [options] distributor-id repo-id
    """
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if len(args) != 2:
        parser.error('You must provide the distributor name and repo id')
    result = p.associate(args[0], args[1])
    log.info("Created distributor: %s", result['id'])


@make_parser
def do_clone(bopts, bargs, parser):
    """Clone a docker repo, bringing content along.

    dock-pulp clone [options] repo-id new-product-line new-image-name
    dock-pulp clone [options] --library repo-id  new-image-name
    """
    parser.add_option('-l', '--library', help='create a "library"-level repo',
                      default=False, action='store_true')
    parser.add_option('--noprefix', help='do not add prefix to the repo id', default=False,
                      action='store_true')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    productid = None
    prefix_with = '' if opts.noprefix else p.getPrefix()
    if opts.library:
        if len(args) != 2:
            parser.error('You need a source repo id and a name for a library-level repo')
        repoid = '%s%s' % (prefix_with, args[1])
    else:
        if len(args) != 3:
            parser.error('You need a source repo id, a new product line '
                         '(rhel6, openshift3, etc), and a new image name')
        repoid = '%s%s-%s' % (prefix_with, args[1], args[2])
        productid = args[1]

    log.info('cloning %s repo to %s' % (args[0], repoid))
    oldinfo = p.listRepos(args[0], content=True)[0]
    dist = oldinfo.get('distribution')
    p.createRepo(repoid, oldinfo['redirect'],
                 desc=oldinfo['description'], title=oldinfo['title'],
                 protected=get_bool_from_string(oldinfo['protected']), distribution=dist,
                 productline=productid, prefix_with=prefix_with)
    log.info('cloning content in %s to %s' % (args[0], repoid))
    if len(oldinfo['images']) > 0:
        for img in oldinfo['images'].keys():
            p.copy(repoid, img)
            tags = {'tag': '%s:%s' % (','.join(oldinfo['images'][img]), img)}
            p.updateRepo(repoid, tags)
    if len(oldinfo['manifests']) > 0:
        for manifest in oldinfo['manifests'].keys():
            p.copy(repoid, manifest)
    if len(oldinfo['images']) == 0 and len(oldinfo['manifests']) == 0:
        log.info('no content to copy in')
    log.info('cloning complete')


@make_parser
def do_confirm(bopts, bargs, parser):
    """Confirm all images are reachable. Accepts regex.

    dock-pulp confirm [options] [repo-id...]
    """
    parser.add_option('-c', '--cert', action='store',
                      help='A cert used to authenticate protected repositories')
    parser.add_option('-k', '--key', action='store',
                      help='A key used to authenticate protected repositories')
    parser.add_option('-s', '--silent', action='store_true', default=False,
                      help='Return confirm output in machine readable form')
    parser.add_option('--check-layers', action='store_true', default=False,
                      help="Tests all layers via shasum for v2 or tar/gzip for v1")
    parser.add_option('--v1', action='store_true', default=False, help='Only report v1 output')
    parser.add_option('--v2', action='store_true', default=False, help='Only report v2 output')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    c = dockpulp.Crane(p, opts.cert, opts.key)

    if opts.silent:
        log.removeHandler(sh)
        log.addHandler(dockpulp.NullHandler())

    rids = None
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

    repoids = c.confirm(rids, opts.v1, opts.v2, opts.silent, opts.check_layers)

    log.info('Testing complete... %s error(s)' % repoids['numerrors'])

    if opts.silent:
        log.addHandler(silent)
        log.info(repoids)

    if repoids['numerrors'] >= 1:
        sys.exit(1)


@make_parser
def do_copy(bopts, bargs, parser):
    """Copy an image from one repo to another.

    dock-pulp copy [options] dest-repo-id image-id [image-id...]
    """
    # TODO: copy over ancestors too
    parser.add_option('-s', '--source', help='specify a source repo to copy from')
    opts, args = parser.parse_args(bargs)
    if len(args) < 2:
        parser.error('You must provide a destination repository and image-id')
    p = pulp_login(bopts)
    for img in args[1:]:
        if opts.source:
            p.copy(args[0], img, opts.source)
        else:
            p.copy(args[0], img)
        log.info('copying successful')


@make_parser
def do_create(bopts, bargs, parser):
    """Create a repository for docker images.

    dock-pulp create [options] product-line image-name content-url
    dock-pulp create [options] --library image-name content-url

    * content-url is not required if redirect-url = no in /etc/dockpulp.conf
    """
    parser.add_option('-d', '--description', help='specify a repo description',
                      default='No description')
    parser.add_option('-l', '--library', help='create a "library"-level repo',
                      default=False, action='store_true')
    parser.add_option('-t', '--title', help='set the title for the repo')
    parser.add_option('--distribution', help='set the distribution field for the repo')
    parser.add_option('-p', '--protected', help='set the protected bit to true for the repo',
                      default=False, action='store_true')
    parser.add_option('--noprefix', help='do not add prefix to the repo id', default=False,
                      action='store_true')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    url = None
    productid = None
    prefix_with = '' if opts.noprefix else p.getPrefix()
    if opts.library:
        if len(args) != 2 and p.isRedirect():
            parser.error('You need a name for a library-level repo and a content-url')
        elif (len(args) != 1 and len(args) != 2) and not p.isRedirect():
            parser.error('You need a name for a library-level repo')
        repoid = '%s%s' % (prefix_with, args[0])
        imagename = args[0]
        if len(args) == 2:
            url = args[1]
    else:
        if len(args) != 3 and p.isRedirect():
            parser.error('You need a product line (rhel6, openshift3, etc),'
                         'image name and a content-url')
        elif (len(args) != 2 and len(args) != 3) and not p.isRedirect():
            parser.error('You need a product line (rhel6, openshift3, etc) and image name')
        productid = args[0]
        imagename = args[1]
        repoid = '%s%s-%s' % (prefix_with, args[0], args[1])
        if len(args) == 3:
            url = args[2]

    if url:
        if not url.startswith('/content'):
            parser.error('the content-url needs to start with /content')
        suffix = '/%s' % imagename
        if productid:
            suffix = '/%s%s' % (productid, suffix)
        if not url.rstrip('/').endswith(suffix):
            parser.error('the content-url needs to end with %s' % suffix)

    p.createRepo(repoid, url, desc=opts.description, title=opts.title, protected=opts.protected,
                 productline=productid, library=opts.library, distribution=opts.distribution,
                 prefix_with=prefix_with)
    log.info('repository created')


@make_parser
def do_delete(bopts, bargs, parser):
    """Delete a repository; this will not affect content in other repos.

    dock-pulp delete [options] repo-id [repo-id...]
    """
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


@make_parser
def do_disassociate(bopts, bargs, parser):
    """Disassociate a distributor from a repo.

    dock-pulp disassociate [options] distributor-id repo-id
    """
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    if len(args) != 2:
        parser.error('You must provide the distributor name and repo id')
    p.disassociate(args[0], args[1])


@make_parser
def do_empty(bopts, bargs, parser):
    """Remove all contents in a repository.

    dock-pulp empty [options] repo-id [repo-id]
    """
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


@make_parser
def do_imageids(bopts, bargs, parser):
    """List all layers existing on server.

    dock-pulp imageids [options] image-id
    """
    opts, args = parser.parse_args(bargs)
    if len(args) == 0:
        parser.error('You must provide an image ID(s)')
    p = pulp_login(bopts)
    result = p.getImageIdsExist(args)
    log.info(result)


@make_parser
def do_list(bopts, bargs, parser):
    """List one or more repositories. Accepts regex.

    dock-pulp list [options] [repo-id...]
    """
    parser.add_option('-c', '--content', default=False, action='store_true',
                      help='also return information about images in a repository')
    parser.add_option('-d', '--details', default=False, action='store_true',
                      help='show details (not content) about each repository')
    parser.add_option('--history', default=False, action='store_true',
                      help='show v1 compatibility history')
    parser.add_option('-l', '--labels', default=False, action='store_true',
                      help='show labels')
    parser.add_option('-m', '--manifests', default=False, action='store_true',
                      help='only list manifests and their tags, no blobs')
    parser.add_option('-s', '--silent', default=False, action='store_true',
                      help='return a json object of the listing, no other output')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)

    if opts.silent:
        log.removeHandler(sh)
        log.addHandler(dockpulp.NullHandler())

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
        repos = p.listRepos(repos=rids, content=opts.content, history=(opts.history or opts.labels),
                            labels=opts.labels)

    if opts.silent:
        log.addHandler(silent)
        repoinfo = json.dumps(repos)
        log.info(repoinfo)
        return

    for repo in repos:
        log.info(repo['id'])
        if opts.details or opts.content:
            log.info('-' * len(repo['id']))
        if opts.details:
            for k, v in repo.items():
                if k in ('id', 'images', 'manifests', 'sigstore'):
                    continue
                else:
                    log.info('%s = %s', k, v)
        if opts.content or opts.history or opts.labels:
            if repo['id'] == p.getSigstore():
                log.info('  Signatures: ')
                for sig in repo['sigstore']:
                    log.info('    %s', sig)
                log.info('')
                continue

            log.info('v1 image details:')
            if len(repo['images'].keys()) == 0:
                log.info('  No images')
            else:
                imgs = repo['images'].keys()
                imgs.sort()
                for img in imgs:
                    log.info('  %s (tags: %s)',
                             img, ', '.join(repo['images'][img]))
                    if opts.labels and repo['v1_labels'][img]:
                        log.info('    Labels:')
                        for key in repo['v1_labels'][img]:
                            log.info('      %s: %s', key, repo['v1_labels'][img][key])
            log.info('')
            log.info('v2 manifest details:')
            if len(repo['manifests'].keys()) == 0:
                log.info('  No manifests')
            else:
                manifests = repo['manifests'].keys()
                manifests.sort()
                tags = repo['tags']
                output = {}
                for manifest in manifests:
                    layer = tuple(repo['manifests'][manifest]['layers'])

                    output.setdefault(layer, {})
                    output[layer].setdefault(manifest, {})

                    tag = repo['manifests'][manifest]['tag']
                    output[layer][manifest]['tag'] = tag

                    active_marker = ''
                    # Is there a docker_tag unit for this name?
                    if tag in tags:
                        # Does it reference this manifest?
                        if tags[tag] == manifest:
                            active_marker = ' (active)'

                    output[layer][manifest]['active'] = active_marker

                    if (opts.history or opts.labels) and not repo['id'] == dockpulp.HIDDEN:
                        output[layer][manifest]['id'] = repo['manifests'][manifest]['v1id']
                        output[layer][manifest]['parent'] = repo['manifests'][manifest]['v1parent']
                        output[layer][manifest]['labels'] = repo['manifests'][manifest]['v1labels']

                images = output.keys()
                for image in images:
                    log.info('')
                    manifests = output[image].keys()
                    tagoutput = []
                    for manifest in manifests:
                        tag = output[image][manifest]['tag']
                        is_active = output[image][manifest]['active']
                        if tag is None:
                            log.info('  Manifest: %s', manifest)
                        else:
                            log.info('  Manifest: %s  Tag: %s%s', manifest, tag, is_active)
                        if is_active:
                            tagoutput.append(tag)
                    if not opts.manifests:
                        log.info('    Blobs: ')
                        for layer in image:
                            log.info('      %s', layer)
                    if opts.history and not repo['id'] == dockpulp.HIDDEN:
                        tagoutput.sort()
                        if output[image][manifests[0]]['id'] or \
                           output[image][manifests[0]]['parent']:
                            log.info('    v1Compatibility:')
                            if output[image][manifests[0]]['id']:
                                log.info('      %s (tags: %s)', output[image][manifests[0]]['id'],
                                         ', '.join(tagoutput))
                            if output[image][manifests[0]]['parent']:
                                log.info('      %s (tags: )', output[image][manifests[0]]['parent'])

                    if opts.labels and not repo['id'] == dockpulp.HIDDEN:
                        if output[image][manifests[0]]['labels']:
                            log.info('    Labels:')
                            for key in output[image][manifests[0]]['labels']:
                                log.info('      %s: %s', key,
                                         output[image][manifests[0]]['labels'][key])

        if opts.details or opts.content or opts.history:
            log.info('')


@make_parser
def do_login(bopts, bargs, parser):
    """Login into pulp and get a session certificate.

    dock-pulp login [options]
    """
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


@make_parser
def do_json(bopts, bargs, parser):
    """Dump the Pulp configuration in an environment in a json format.

    dock-pulp json [options] [2> file.json]
    """
    parser.add_option('-p', '--pretty', default=False, action='store_true',
                      help='format the json into something human-readable')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    j = p.dump(pretty=opts.pretty)
    log.info('json dump follows this line on stderr')
    print >> sys.stderr, j


@make_parser
def do_release(bopts, bargs, parser):
    """Publish pulp configurations to Crane, making them live. Accepts regex.

    dock-pulp release [options] [repo-id...]
    """
    parser.add_option('-s', '--skip-fast-forward', default=False, action='store_true',
                      dest="skip", help='use skip fast forward for release')
    parser.add_option('-r', '--force-refresh', default=False, action='store_true',
                      dest="force_refresh",
                      help='removes extra content on filer that is not in pulp')
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
        p.crane(repos=rids, skip=opts.skip, force_refresh=opts.force_refresh)
    log.info('pulp configuration(s) successfully exported')


@make_parser
def do_orphans(bopts, bargs, parser):
    """List orphaned content with option to remove it.

    dock-pulp orphans [--remove]
    """
    parser.add_option('-r', '--remove', default=False, action='store_true',
                      help='Remove all orphaned content. USE WITH CAUTION')
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)

    for content_type in (dockpulp.V1_C_TYPE,
                         dockpulp.V2_C_TYPE,
                         dockpulp.V2_BLOB):
        orphans = p.listOrphans(content_type)
        pretty_content_type = content_type.replace('_', ' ') + 's'
        log.info('Orphan %s:' % pretty_content_type)

        if len(orphans) == 0:
            log.info('  No orphans found')
        for orphan in orphans:
            display_id = orphan.get('image_id') or orphan.get('digest')
            log.info('  %s' % display_id)

        if opts.remove:
            log.info('removing all orphaned %s' % pretty_content_type)
            p.cleanOrphans(content_type)
            log.info('Orphaned %s removed' % pretty_content_type)


@make_parser
def do_remove(bopts, bargs, parser):
    """Remove an image from a repo, or clean up orphaned content.

    dock-pulp remove [options] repo-id image-id [image-id...]
    dock-pulp remove --list-orphans [--remove]
    """
    # TODO: figure out how to remove unneeded layers too
    parser.add_option('-l', '--list-orphans', default=False,
                      action='store_true', help='list orphaned images')
    parser.add_option('-r', '--remove', default=False, action='store_true',
                      help='Remove all orphaned content. USE WITH CAUTION')
    opts, args = parser.parse_args(bargs)
    if opts.list_orphans:
        log.warning('DEPRECATED: Use dock-pulp orphans instead.')
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
    if args[0] == dockpulp.HIDDEN:
        log.info('removed images')
        sys.exit(0)

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


@make_parser
def do_sync(bopts, bargs, parser):
    """Sync a repo from one environment to another.

    dock-pulp sync [options] <env to sync from> repo-id
    """
    parser.add_option('-p', '--password', help='specify a password')
    parser.add_option('-u', '--username', help='specify a username')
    parser.add_option('--upstream', help='specify an upstream name docker id to sync from')
    opts, args = parser.parse_args(bargs)
    if len(args) < 2:
        parser.error('You must provide an environment to sync from and a repo id')
    p = pulp_login(bopts)
    env = args[0]
    repo = args[1]

    imgs, manifests = p.syncRepo(env, repo, bopts.config_file, basic_auth_username=opts.username,
                                 basic_auth_password=opts.password, upstream_name=opts.upstream)

    log.info(repo)
    log.info('-' * len(repo))
    log.info('synced images:')

    if len(imgs) == 0:
        log.info('  No new images')
    else:
        for img in imgs:
            log.info(img)
    log.info('')

    if len(manifests) == 0:
        log.info('  No new manifests')
    else:
        for manifest in manifests:
            log.info(manifest)
    log.info('')


@make_parser
def do_tag(bopts, bargs, parser):
    """Tag an image with a tag in a repo.

    dock-pulp tag [options] repo-id image-id tags,with,commas
    dock-pulp tag [options] --remove repo-id image-id
    """
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


@make_parser
def do_task(bopts, bargs, parser):
    """Display information about a task in pulp.

    dock-pulp task [options] task-id [task-id...]
    """
    opts, args = parser.parse_args(bargs)
    if len(args) < 1:
        parser.error('You must provide a task ID')
    p = pulp_login(bopts)
    for task in args:
        taskinfo = p.getTask(task)
        log.info(taskinfo['task_id'])
        log.info('-' * 36)
        for field in ('state', 'error', 'task_type', 'queue', 'start_time',
                      'finish_time', 'traceback'):
            if field not in taskinfo:
                continue
            log.info('%s = %s' % (field, taskinfo[field]))


@make_parser
def do_update(bopts, bargs, parser):
    """Update metadata for a docker image repository.

    dock-pulp update [options] repo-id [repo-id...]
    """
    parser.add_option('-d', '--description',
                      help='update the description for this repository')
    parser.add_option('-i', '--dockerid',
                      help='set the docker ID (name) for this repo')
    parser.add_option('-r', '--redirect', help='set the redirect URL')
    parser.add_option('-t', '--title', help='set the title (short desc)')
    parser.add_option('-s', '--signature', help='set the signatures field for the repo')
    parser.add_option('--distribution', help='set the distribution field for the repo')
    parser.add_option('-p', '--protected',
                      help='set the protected bit. Accepts (t, true, True) for True, '
                           '(f, false, False) for False')
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
    if opts.signature:
        updates['signature'] = opts.signature
    if opts.distribution:
        updates['distribution'] = opts.distribution
    if opts.protected:
        updates['protected'] = get_bool_from_string(opts.protected)
    for repo in args:
        p.updateRepo(repo, updates)
        log.info('repo successfully updated')


@make_parser
def do_upload(bopts, bargs, parser):
    """Upload an image to a pulp repository.

    dock-pulp upload image-path [repo-id...]
    dock-pulp upload --list-uploads [--delete]
    """
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
