#!/usr/bin/python -tt
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
import simplejson as json
import sys

import dockpulp


log = dockpulp.setup_logger(dockpulp.log)

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
    except dockpulp.errors.DockPulpInternalError, pe:
        log.error('Internal failure: %s' % str(pe))
    except dockpulp.errors.DockPulpLoginError, pe:
        log.error('Login Error: %s' % str(pe))
        log.error(
            'Did you log into the %s environment with the right password?' %
            opts.server)
    except dockpulp.errors.DockPulpServerError, pe:
        log.error('Server-side problem: %s' % str(pe))
        log.error('')
        log.error('The only recourse here is to contact IT. :(')
    except dockpulp.errors.DockPulpTaskError, pe:
        log.error('Subtask failed: %s' % pe)
        log.error('')
        log.error('Use the "task" command to see the full traceback')
        log.error('Use --debug to see inspect the server request')
    except dockpulp.errors.DockPulpError, pe:
        log.error('Error: %s' % str(pe))
        log.error('')
        log.error('For help diagnosing errors, go to the link below. The API')
        log.error('we used is shown above with the HTTP response code.')
        log.error('   http://pulp-dev-guide.readthedocs.org/en/latest/integration/index.html')

def pulp_login(bopts):
    p = dockpulp.Pulp(env=bopts.server, config_file=bopts.config_file)
    if bopts.debug:
        p.setDebug()
    if bopts.cert and bopts.key:
        p.certificate = bopts.cert
        p.key = bopts.key
    elif not os.path.exists(os.path.join(os.path.expanduser('~/.pulp'), 'pulp.cer')):
        log.error('You need to log in with a user/password first.')
        sys.exit(1)
    else:
        creddir = os.path.expanduser('~/.pulp')
        p.certificate = os.path.join(creddir, 'pulp.cer')
        p.key = os.path.join(creddir, 'pulp.key')
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

def _test_repo(dpo, dockerid, redirect, pulp_imgs):
    """confirm we can reach crane and get data back from it"""
    # manual: curl --insecure https://registry.access.stage.redhat.com/v1/repositories/rhel6/rhel/images
    #         curl --insecure https://registry.access.stage.redhat.com/v1/repositories/rhel6.6/images
    url = dpo.registry + '/' + dockerid + '/images'
    log.info('  Testing Pulp and Crane data')
    log.debug('  contacting %s' % url)
    answer = requests.get(url, verify=False)
    log.debug('  crane content: %s' % answer.content)
    log.debug('  status code: %s' % answer.status_code)
    if answer.content == 'Not Found':
        log.error('  Crane returned a 404')
        return False
    try:
        j = json.loads(answer.content)
    except ValueError, ve:
        log.error('  Crane did not return json')
        return False
    p_imgs = set(pulp_imgs)
    c_imgs = set([i['id'] for i in j])
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
        return False
    log.info('  Pulp and Crane data reconciled correctly, testing content')
    missing = set([])
    for img in pulp_imgs:
        for ext in ('json', 'ancestry', 'layer'):
            url = redirect + '/' + img + '/' + ext
            log.debug('  reaching for %s' % url)
            with closing(requests.get(url, verify=False, stream=True)) as answer:
                log.debug('    got back a %s' % answer.status_code)
                if answer.status_code != 200:
                    missing.add(img)
    if len(missing) > 0:
        log.error('  Could not reach images:')
        log.error('    ' + ', '.join(missing))
        return False
    log.info('  All images are reachable, tests pass.')
    return True

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

def do_clone(bopts, bargs):
    """
    dock-pulp clone [options] repo-id new-repo-id
    Clone a docker repo, bringing content along"""
    parser = OptionParser(usage=do_clone.__doc__)
    opts, args = parser.parse_args(bargs)
    if len(args) != 2:
        parser.error('You must provide a source repo id and new repo id')
    p = pulp_login(bopts)
    log.info('cloning %s repo to %s' % (args[0], args[1]))
    oldinfo = p.listRepos(args[0], content=True)[0]
    newrepo = p.createRepo(args[1], oldinfo['redirect'],
        desc=oldinfo['description'], title=oldinfo['title'])
    log.info('cloning content in %s to %s' % (args[0], args[1]))
    if len(oldinfo['images']) > 0:
        for img in oldinfo['images'].keys():
            p.copy(args[1], img)
            tags = {'tag': '%s:%s' % (','.join(oldinfo['images'][img]), img)}
            p.updateRepo(args[1], tags)
    else:
        log.info('no content to copy in')
    log.info('cloning complete')

def do_confirm(bopts, bargs):
    """
    dock-pulp confirm [options] [repo-id...]
    Confirm all images are reachable. Accepts globs!"""
    parser = OptionParser(usage=do_clone.__doc__)
    opts, args = parser.parse_args(bargs)
    p = pulp_login(bopts)
    rids = None
    if len(args) > 0:
        rids = []
        for arg in args:
            if '*' in arg or '?' in arg:
                results = p.searchRepos(arg)
                if len(results) == 0:
                    log.warning('Glob did not match anything')
                    return
                else:
                    rids.extend(results)
            else:
                rids.append(arg)
    repos = p.listRepos(repos=rids, content=True)
    errors = 0
    for repo in repos:
        log.info('Testing %s' % repo['id'])
        imgs = repo['images'].keys()
        if not _test_repo(p, repo['docker-id'], repo['redirect'], imgs):
            errors += 1
    log.info('Testing complete... %s error(s)' % errors)

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
    Create a repository for docker images"""
    parser = OptionParser(usage=do_create.__doc__)
    parser.add_option('-d', '--description', help='specify a repo description',
        default='No description')
    parser.add_option('-l', '--library', help='create a "library"-level repo',
        default=False, action='store_true')
    parser.add_option('-t', '--title', help='set the title for the repo')
    opts, args = parser.parse_args(bargs)
    if opts.library:
        if len(args) != 2:
            parser.error('You need a name for a library-level repo and a content-url')
        id = 'redhat-%s' % (args[0])
        url = args[1]
    else:
        if len(args) != 3:
            parser.error('You need a product line (rhel6, openshift3, etc), image name and a content-url')
        id = 'redhat-%s-%s' % (args[0], args[1])
        url = args[2]
    if not url.startswith('/content'):
        parser.error('the content-url needs to start with /content')
    p = pulp_login(bopts)
    p.createRepo(id, url, desc=opts.description, title=opts.title)
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
        p.deleteRepo(repo)
        log.info('deleted %s' % repo)

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

def do_list(bopts, bargs):
    """
    dock-pulp list [options] [repo-id...]
    List one or more repositories. Accepts globs!"""
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
                    log.warning('Glob did not match anything')
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
            log.info('image details:')
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

def do_push_to_pulp(bopts, bargs):
    """
    dock-pulp push_to_pulp <tar_file> <name[:tag]>
    Push images to pulp <name> repository and tag top-layer image with tag
    """
    #parser = OptionParser(usage=do_json.__doc__)
    #parser.add_option('-p', '--pretty', default=False, action='store_true',
    #    help='format the json into something human-readable')
    #opts, args = parser.parse_args(bargs)
    parser = OptionParser(usage=do_push_to_pulp.__doc__)
    parser.add_option('-d', '--desc',
                      help='New repo description (only if repo doesn\'t exist)')
    parser.add_option('-l', '--label',
                      help='New repo label (only if repo doesn\'t exist)')
    parser.add_option('-r', '--registry-id',
                      help='Registry id (only if repo doesn\'t exist)')
    opts, args = parser.parse_args(bargs)
    if len(args) < 2:
        raise ValueError("push_to_pulp accepts 2 arguments")
    p = pulp_login(bopts)
    tar_file = args[0]
    repo,tag = (None,None)
    splitted = args[1].split(":")
    repo = splitted[0]
    if len(splitted) > 1:
        tag = splitted[1]

    if opts.label or opts.desc:
        missing_repos_info = {}
        missing_repos_info[repo] = {"desc": opts.desc, "title": opts.label}
    else:
        missing_repos_info = None
    registry_id = opts.registry_id or \
        repo.replace('redhat-', '').replace('-', '/', 1)

    repo_tag_mapping = {
        repo: {"tags": [tag],
               "registry-id": registry_id
        }
    }
    p.push_tar_to_pulp(repo_tag_mapping, tar_file,
                       missing_repos_info=missing_repos_info)

    p.crane([repo])

def do_release(bopts, bargs):
    """
    dock-pulp release [options] [repo-id...]
    Publish pulp configurations to Crane, making them live. Accepts globs!"""
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
                    log.warning('Glob did not match anything')
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
    metadata = dockpulp.imgutils.get_metadata(args[0])
    newimgs = dockpulp.imgutils.get_metadata_pulp(metadata).keys()
    log.info('Layers in this tarball:')
    for img in newimgs:
        log.info('  %s' % img)
    vers = dockpulp.imgutils.get_versions(metadata)
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
