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

import atexit
import ConfigParser
import logging
import os
import pickle
import pprint
import requests
import shutil
import sys
import tempfile
import time

import multiprocessing

try:
    import json
except ImportError:
    # Python 2.6 and earlier
    import simplejson as json

import errors
import imgutils

C_TYPE = 'docker_image'         # pulp content type identifier for docker
HIDDEN = 'redhat-everything'    # ID of a "hidden" repository for RCM
DEFAULT_CONFIG_FILE = '/etc/dockpulp.conf'


# Setup our logger
# Null logger to avoid spurious messages, add a handler in app code
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


# This is our log object, clients of this library can use this object to
# define their own logging needs
log = logging.getLogger("dockpulp")

# Add the null handler
h = NullHandler()
log.addHandler(h)


class RequestsHttpCaller(object):
    def __init__(self, url):
        self.url = url
        self.certificate = None

    def _error(self, code, url):
        """format a nice error message"""
        raise errors.DockPulpError('Received response %s from %s' % (code, url))

    def __call__(self, meth, api, **kwargs):
        """post an http request to a Pulp API"""
        log.debug('remote host is %s' % self.url)
        c = getattr(requests, meth)
        url = self.url + api
        if self.certificate:
            kwargs['cert'] = (self.certificate, self.key)
        kwargs['verify'] = False # TODO: figure out when to make True
        log.debug('calling %s on %s' % (meth, url))
        if 'uploads' not in api:
            # prevent printing for uploads, since that will print megabytes of
            # text to the screen uselessly
            log.debug('kwargs: %s' % kwargs)
        try:
            answer = c(url, **kwargs)
        except requests.exceptions.SSLError, se:
            raise errors.DockPulpLoginError('Expired or bad certificate, please re-login')
        try:
            r = json.loads(answer.content)
            log.debug('raw response data:')
            log.debug(pprint.pformat(r))
        except ValueError:
            log.warning('No content in Pulp response')
        if answer.status_code == 403:
            raise errors.DockPulpLoginError('Received 403: Forbidden')
        elif answer.status_code >= 500:
            raise errors.DockPulpServerError('Received a 500 error')
        elif answer.status_code >= 400:
            self._error(answer.status_code, url)
        elif answer.status_code == 202:
            log.info('Pulp spawned a subtask: %s' % 
                r['spawned_tasks'][0]['task_id'])
            # TODO: blindly takes the first task only
            return r['spawned_tasks'][0]['task_id']
        return r

    """
    def _get(self, api, **kwargs):
        return self._request('get', api, **kwargs)

    def _post(self, api, **kwargs):
        return self._request('post', api, **kwargs)

    def _put(self, api, **kwargs):
        return self._request('put', api, **kwargs)

    def _delete(self, api, **kwargs):
        return self._request('delete', api, **kwargs)
    """

class Pulp(object):
    def __init__(self, env='qa', config_file=DEFAULT_CONFIG_FILE):
        """
        The constructor only sets up the remote hostname given an environment.
        Accepts shorthand, or full hostnames.
        """
        self.certificate = None # set in login()
        self.key = None
        self.env = env
        conf = ConfigParser.ConfigParser()
        if not config_file:
            raise errors.DockPulpConfigError('Missing config file')
        conf.readfp(open(config_file))
        for sect in ('pulps', 'registries', 'filers'):
            if not conf.has_section(sect):
                raise errors.DockPulpConfigError('Missing section: %s' % sect)
            if not conf.has_option(sect, env):
                raise errors.DockPulpConfigError('%s section is missing %s' %
                    (sect, env))
        self.url = conf.get('pulps', env)
        self._request = RequestsHttpCaller(conf.get('pulps', env))
        self.registry = conf.get('registries', env)
        self.cdnhost = conf.get('filers', env)

    def _cleanup(self, creddir):
        """
        Clean up the session cert and key. Called automatically on program exit
        """
        log.debug('cleaning up session credentials')
        shutil.rmtree(creddir, ignore_errors=True)

    def _createUploadRequest(self):
        """create an upload request"""
        log.debug('creating upload request')
        rid = self._post('/pulp/api/v2/content/uploads/')['upload_id']
        log.info('upload request: %s' % rid)
        return rid

    def _deleteUploadRequest(self, rid):
        """delete an upload request"""
        log.debug('deleting upload request since we are done')
        self._delete('/pulp/api/v2/content/uploads/%s/' % rid)
        log.info('removed upload request %s' % rid)

    def _error(self, code, url):
        """format a nice error message"""
        raise errors.DockPulpError('Received response %s from %s' % (code, url))

    def _getTags(self, repo):
        """return the tag list for a given repo"""
        log.debug('getting tag data...')
        params = {'details': True}
        rinfo = self._get('/pulp/api/v2/repositories/%s/' % repo,
             params=params)
        if rinfo['scratchpad'].has_key('tags'):
            return rinfo['scratchpad']['tags']
        else:
            return []

    def _get(self, api, **kwargs):
        return self._request('get', api, **kwargs)

    def _post(self, api, **kwargs):
        return self._request('post', api, **kwargs)

    def _put(self, api, **kwargs):
        return self._request('put', api, **kwargs)

    def _delete(self, api, **kwargs):
        return self._request('delete', api, **kwargs)


    def _enforce_repo_name_policy(self, repos, repo_prefix=None):
        new_repos = []
        for repo in repos:
            if not repo.startswith(repo_prefix):
                new_repo_key = repo_prefix + repo
            else:
                new_repo_key = repo
            new_repos.append(new_repo_key)
        return new_repos


    # public methods start here, alphabetically

    def cleanOrphans(self):
        """
        Remove orphaned docker content
        """
        raise error.DockPulpError('Removing docker orphans not implemented in Pulp 2.4')
        #tid = self._delete('/pulp/api/v2/content/orphans/%s/' % C_TYPE)
        #self.watch(tid)

    def cleanUploadRequests(self):
        """
        Remove outstanding upload requests from Pulp to reclaim space
        """
        uploads = self.listUploadRequests()
        for upload in uploads:
            self._deleteUploadRequest(upload)

    def copy(self, drepo, img):
        """
        Copy an image from one repo to another
        """
        data = {
            'source_repo_id': HIDDEN,
            'criteria': {
                'type_ids' : [C_TYPE],
                'filters' : {
                    'unit' : {
                        'image_id': img
                    }
                }
            },
            'override_config': {}
        }
        log.debug('copy request we are sending:')
        log.debug(pprint.pformat(data))
        log.info('copying %s from %s to %s' % (img, HIDDEN, drepo))
        tid = self._post(
            '/pulp/api/v2/repositories/%s/actions/associate/' % drepo,
            data=json.dumps(data))
        self.watch(tid)

    """
    """
    def crane(self, repos=[], wait=True):
        """
        Export pulp configuration to crane for one or more repositories
        """
        if len(repos) == 0:
            repos = self.getAllRepoIDs()
        tasks = []
        results = []
        if not wait:
            pool = multiprocessing.Pool()

        for repo in repos:
            for did in ('docker_export_distributor_name_cli',
                        'docker_web_distributor_name_cli'):
                log.info('updating distributor: %s' % did)
                url = '/pulp/api/v2/repositories/%s/actions/publish/' % repo
                kwds={"data": json.dumps({'id': did})}
                if not wait:
                    results.append(pool.apply_async(self._request,
                                                    args=("post", url,),
                                                    kwds=kwds))
                else:
                    tid = self._post(url, data=kwds["data"])
                    self.watch(tid)
                    tasks.append(tid)
        if not wait:
            pool.close()
            pool.join()
            return [result.get() for result in results]
        else:
            return tasks

    def createRepo(self, repo_id, url, registry_id=None, desc=None, title=None,
        distributors=True, prefix_with="redhat-"):
        """
        create a docker repository in pulp, an id and a description is required
        """
        if not repo_id.startswith(prefix_with):
            repo_id = prefix_with + repo_id
        if '/' in repo_id:
            log.warning('Looks like you supplied a docker repo ID, not pulp')
            raise errors.DockPulpError('Pulp repo ID cannot have a "/"')
        if registry_id is None:
            registry_id = repo_id.replace('redhat-', '').replace('-', '/', 1)
            if '/' in registry_id:
                if '-' in registry_id[:registry_id.index('/')]:
                    log.warning('docker-pull does not support this repo ID')
                    raise errors.DockPulpError('Docker repo ID has a hyphen before the "/"')
        rurl = url
        if not rurl.startswith('http'):
            rurl = self.cdnhost + url
        if not desc:
            desc = 'No description'
        if not title:
            title = repo_id
        log.info('creating repo %s' % repo_id)
        log.info('docker ID is %s' % registry_id)
        log.info('redirect is %s' % rurl)
        stuff = {
            'id': repo_id,
            'description': desc,
            'display_name': title,
            'importer_type_id': 'docker_importer',
            'importer_config': {},
            'notes': {'_repo-type': 'docker-repo'},
        }
        if distributors:
            stuff['distributors'] = [{
                'distributor_id': 'docker_export_distributor_name_cli',
                'distributor_type_id': 'docker_distributor_export',
                'distributor_config': {
                    'protected': False,
                    'repo-registry-id': registry_id,
                    'redirect-url': rurl
                },
                'auto_publish': True
            }, {
                'distributor_id': 'docker_web_distributor_name_cli',
                'distributor_type_id': 'docker_distributor_web',
                'distributor_config': {
                    'protected': False,
                    'repo-registry-id': registry_id,
                    'redirect-url': rurl
                },
                'auto_publish': True
            }]
        else:
            stuff['distributors'] = []
        log.debug('data sent in request:')
        log.debug(pprint.pformat(stuff))
        self._post('/pulp/api/v2/repositories/', data=json.dumps(stuff))

    def deleteRepo(self, id):
        """
        delete a repository; cannot be undone!
        """
        log.info('deleting repo: %s' % id)
        tid = self._delete('/pulp/api/v2/repositories/%s/' % id)
        self.watch(tid)

    def dump(self, pretty=False):
        """
        dump the complete configuration of an environment to json format
        """
        if pretty:
            return json.dumps(self.listRepos(content=True),
                sort_keys=True, indent=2)
        else:
            return json.dumps(self.listRepos(content=True))

    def exists(self, rid):
        """
        Return True if a repository already exists, False otherwise
        """
        data = {'criteria':
                    {'filters':
                        {'id': rid}
                    },
                'fields': ['id']
                }
        found = self._post('/pulp/api/v2/repositories/search/',
            data=json.dumps(data))
        return len(found) > 0

    def getAllRepoIDs(self):
        """
        Get all repository IDs in Pulp
        """
        repos = []
        log.info('getting all repositories...')
        params = {'details': True}
        for blob in self._get('/pulp/api/v2/repositories/', params=params):
            repos.append(blob['id'])
        repos.sort()
        repos.remove(HIDDEN) # remove the RCM-internal repository
        return repos

    def getAncestors(self, iid, parents=[]):
        """
        Return the list of layers (ancestors) of a given image
        """
        # a rest call is made per parent, which impacts performance greatly
        data = {
            'criteria': {
                'filters' : {
                    'unit' : {
                        'image_id': iid
                    }
                },
            'limit': 1,
            },
        }
        log.debug('search request:')
        log.debug(json.dumps(data))
        img = self._post('/pulp/api/v2/repositories/%s/search/units/' % HIDDEN,
            data=json.dumps(data))[0]
        par = img['metadata']['parent_id']
        if par is not None:
            parents.append(par)
            return self.getAncestors(par, parents=parents)
        else:
            return parents

    def getTask(self, tid):
        """
        return a task report for a given id
        """
        log.debug('getting task %s information' % tid)
        return self._get('/pulp/api/v2/tasks/%s/' % tid)

    def getTasks(self, tids):
        """
        return a task report for a given id
        """
        log.debug('getting tasks %s information' % tids)
        criteria = json.dumps({"criteria":{"filters":{"task_id":{"$in":tids}}}})
        return self._post('/pulp/api/v2/tasks/search/', data=criteria)

    def listOrphans(self):
        """
        return a list of orphaned content
        """
        log.debug('getting list of orphaned docker_images')
        return self._get('/pulp/api/v2/content/orphans/%s/' % C_TYPE)

    def listRepos(self, repos=None, content=False):
        """
        Return information about pulp repositories
        If repos is a string or list of strings, treat them as repo IDs
        and get information about each one. If None, get all repos.
        """
        blobs = []
        params = {'details': True}
        if not repos:
            # get all repository IDs first since none were specified
            repos = self.getAllRepoIDs()
        if type(repos) == str:
            repos = [repos]
        # return information for each repo
        for repo in repos:
            blobs.append(self._get('/pulp/api/v2/repositories/%s/' % repo,
                params=params))
        clean = []
        # From here we trim out data nobody cares about
        # we assume distributors have the same configuration
        for blob in blobs:
            if blob['notes']['_repo-type'] != 'docker-repo':
                raise errors.DockPulpError('Non-docker repo hit, what should I do?!')
            r = {
                'id': blob['id'],
                'description': blob['description'],
                'title': blob['display_name']
            }
            if len(blob['distributors']) > 0:
                r['protected'] = blob['distributors'][0]['config']['protected']
                r['redirect'] = blob['distributors'][0]['config']['redirect-url']
                r['docker-id'] = blob['distributors'][0]['config']['repo-registry-id']
            if content:
                data = {
                    'criteria': {
                        'type_ids': [C_TYPE],
                        'filters': {
                            'unit': {}
                        }
                    }
                }
                log.debug('getting image information with request:')
                log.debug(pprint.pformat(data))
                imgs = self._post(
                    '/pulp/api/v2/repositories/%s/search/units/' % blob['id'],
                    data=json.dumps(data))
                r['images'] = {}
                for img in imgs:
                    r['images'][img['metadata']['image_id']] = []
                if blob['scratchpad'].has_key('tags'):
                    tags = blob['scratchpad']['tags']
                    for tag in tags:
                        try:
                            r['images'][tag['image_id']].append(tag['tag'])
                        except KeyError:
                            log.warning('stale scratch pad data found!')
                            log.warning(
                                '%s here but not in repo!' % tag['image_id'])
                        r['images'][tag['image_id']].sort()
            clean.append(r)
            clean.sort()
        return clean

    def listUploadRequests(self):
        """return a pending upload requests"""
        log.debug('getting all upload IDs')
        return self._get('/pulp/api/v2/content/uploads/')['upload_ids']

    def login(self, user, password):
        """
        Log into pulp using a user/pass combo. A certificate is saved for
        additional logins.
        """
        log.info('logging in as %s' % user)
        if not self._request.certificate:
            blob = self._post('/pulp/api/v2/actions/login/',
                auth=(user, password))
            sessiondir = tempfile.mkdtemp()
            log.debug('session info saved in %s' % sessiondir)
            for part in ('certificate', 'key'):
                # save the cert and key for future calls
                f = os.path.join(sessiondir, 'pulp.' + part[:3])
                fd = open(f, 'w')
                fd.write(blob[part])
                fd.close()
                setattr(self._request, part, f)
                setattr(self, part, f)
            atexit.register(self._cleanup, sessiondir)

    def logout(self):
        """
        Log out. Does nothing except clean up session info if necessary. There
        is no need to call this function.
        """
        log.info('logging out')
        if self.certificate:
            self._cleanup(os.path.dirname(self.certificate))

    def push_tar_to_pulp(self, repos_tags_mapping, tarfile, missing_repos_info={},
                         repo_prefix="redhat-"):
        """
        repos_tags_mapping is mapping between repo-ids, registry-ids and tags
        which should be applied to those repos, expected structure:
        {
            "my-image": {
                "registry-id": "nick/my-image",
                "tags": ["v1", "latest"],
            },
            ...
        }
        """
        metadata = imgutils.get_metadata(tarfile)
        pulp_md = imgutils.get_metadata_pulp(metadata)
        imgs = pulp_md.keys()
        mod_repos_tags_mapping = {}
        repos = self._enforce_repo_name_policy(repos_tags_mapping.keys(),
                                               repo_prefix=repo_prefix)
        for new_repo,old_repo in zip(repos,repos_tags_mapping.keys()):
            mod_repos_tags_mapping[new_repo] = repos_tags_mapping[old_repo]

        #repos = mod_repos_tags_mapping.keys()

        found_repos = self._post('/pulp/api/v2/repositories/search/',
                              data=json.dumps({"criteria": {"filters": {"id": {"$in": repos}}},
                                                            "fields": ["id"]}))
        found_repo_ids = [repo["id"] for repo in found_repos]

        # create missing repos
        missing_repos = set(repos) - set(found_repo_ids)
        log.info("Missing repos: %s" % missing_repos)
        for repo in missing_repos:
            kwargs = {}
            #print missing_repos_info
            if repo in missing_repos_info:
                kwargs = {"title": missing_repos_info[repo].get("title"),
                          "desc": missing_repos_info[repo].get("desc")}
                #print kwargs
            self.createRepo(repo, "/pulp/docker/%s" % repo,
                            registry_id=mod_repos_tags_mapping[repo]["registry-id"],
                            desc=kwargs.get("desc"), title=kwargs.get("title"))

        top_layer = imgutils.get_top_layer(pulp_md)
        self.upload(tarfile)

        for repo, repo_conf in mod_repos_tags_mapping.items():
            for img in imgs:
                self.copy(repo, img)
            self.updateRepo(repo, {"tag": "%s:%s" % (",".join(repo_conf["tags"]),
                                                         top_layer)})

    def remove(self, repo, img):
        """
        Remove an image from a repo
        """
        data = {
            'criteria': {
                'type_ids' : [C_TYPE],
                'filters' : {
                    'unit' : {
                        'image_id': img
                    }
                }
            },
            'limit': 1,
            'override_config': {}
        }
        log.debug('removal request we are sending:')
        log.debug(pprint.pformat(data))
        log.info('removing %s from %s' % (img, repo))
        tid = self._post(
            '/pulp/api/v2/repositories/%s/actions/unassociate/' % repo,
            data=json.dumps(data))
        self.watch(tid)

    def searchRepos(self, patt):
        """
        Return a list of existing Pulp repository IDs that match a pattern
        """
        data = {
            'criteria': {
                'filters': {
                    'id': {
                        '$regex': patt
                    }
                },
                'fields': ['id']
            }
        }
        repos = self._post('/pulp/api/v2/repositories/search/',
            data=json.dumps(data))
        return [r['id'] for r in repos]

    def setDebug(self):
        """turn on debug output"""
        log.setLevel(logging.DEBUG)

    def updateRepo(self, rid, update):
        """
        Update metadata on a repository
        "update" is a dictionary of keys to update with new values
        """
        log.info('updating repo %s' % rid)
        export_id = 'docker_export_distributor_name_cli'
        web_id = 'docker_web_distributor_name_cli'
        delta = {
            'delta': {},
            'distributor_configs': {
                export_id: {},
                web_id: {}
            }
        }
        # we intentionally ignore everything else
        valid = ('redirect-url', 'repo-registry-id', 'description', 'display_name', 'tag')
        for u in update.keys():
            if u not in valid:
                log.warning('ignoring %s, not sure how to update' % u)
        for key in ('description', 'display_name'):
            if update.has_key(key):
                delta['delta'][key] = update[key]
        if update.has_key('tag'):
            tags, iid = update['tag'].split(':')
            new_tags = tags.split(",")
            existing = self._getTags(rid) # need to preserve existing tags
            # need to wipe out existing tags for the given image and the
            # existing tags for other images if they match
            existing = [e for e in existing if e["tag"] not in new_tags and
                e['image_id'] != iid]
            log.debug(existing)
            delta['delta']['scratchpad'] = {'tags': existing}
            if tags != '':
                for tag in tags.split(','):
                    delta['delta']['scratchpad']['tags'].append(
                        {'image_id': iid, 'tag': tag})
        for key in ('protected', 'redirect-url', 'repo-registry-id'):
            if update.has_key(key):
                delta['distributor_configs'][export_id][key] = update[key]
                delta['distributor_configs'][web_id][key] = update[key]
        if len(delta['distributor_configs']) == 0:
            log.info('  no need to update the distributor configs')
            delta.pop('distributor_configs')
        log.debug('update request body: %s' % pprint.pformat(delta))
        tid = self._put('/pulp/api/v2/repositories/%s/' % rid,
            data=json.dumps(delta))
        self.watch(tid)

    def upload(self, image):
        """
        Upload an image to pulp. This does not associate it with any repository.
        """
        # TODO: support a hidden repo for "no-channel" style uploads
        rid = self._createUploadRequest()
        size = int(os.path.getsize(image))
        curr = 0
        block = 1024 * 1024 # 1M
        log.info('uploading a %sM image' % (size / block,))
        with open(image) as fobj:
            while curr < size:
                data = fobj.read(block)
                self._put('/pulp/api/v2/content/uploads/%s/%s/' % (rid, curr),
                    data=data)
                curr += len(data)
                log.debug('%s/%s bytes sent' % (curr, size))
        log.info('content uploaded')
        iid = imgutils.get_id(image)
        data = {
            # type_id is from pulp_docker.common.constants.IMAGE_TYPE_ID
            'unit_type_id': C_TYPE,
            'upload_id': rid,
            'unit_key': {'image_id': iid},
            'unit_metadata': {
                'checksum_type': None,
                'filename': os.path.basename(image)
            }
        }
        log.info('adding %s to %s' % (iid, HIDDEN))
        log.debug('repo import request data:')
        log.debug(pprint.pformat(data))
        tid = self._post(
            '/pulp/api/v2/repositories/%s/actions/import_upload/' % HIDDEN,
            data=json.dumps(data))
        timer = max(60, (size/block)*2) # wait 2 seconds per megabyte, or 60,
        self.watch(tid, timeout=timer)  # whichever is greater
        self._deleteUploadRequest(rid)

    def watch(self, tid, timeout=60, poll=5):
        """watch a task ID and return when it finishes or fails"""
        log.info('waiting up to %s seconds for task %s...' % (timeout, tid))
        curr = 0
        while curr < timeout:
            t = self.getTask(tid)
            if t['state'] == 'finished':
                log.info('subtask completed')
                return True
            elif t['state'] == 'error':
                log.debug('traceback from subtask:')
                log.debug(t['traceback'])
                raise errors.DockPulpTaskError(t['error'])
            else:
                log.debug('sleeping (%s/%s seconds passed)' % (curr, timeout))
                time.sleep(poll)
                curr += poll
        log.error('timed out waiting for subtask')
        raise errors.DockPulpError('Timed out waiting for task %s' % tid)

    def watch_tasks(self, tids, timeout=60, poll=5):
        """watch a tasks ID and return when all finishes or fails"""
        log.info('waiting up to %s seconds for task %s...' % (timeout, tids))
        curr = 0
        awaited = tids[:]

        while curr < timeout and awaited:
            states = self.getTasks(awaited)
            for task in states:
                if task['state'] == 'finished':
                    log.info('subtask completed')
                    awaited.pop(awaited.index(task["task_id"]))
                    return True
                elif task['state'] == 'error':
                    log.debug('traceback from subtask:')
                    log.debug(task['traceback'])
                    awaited.pop(awaited.index(task["task_id"]))
                    raise errors.DockPulpTaskError(task['error'])
            log.debug('sleeping (%s/%s seconds passed)' % (curr, timeout))
            time.sleep(poll)
            curr += poll

        log.error('timed out waiting for subtasks')
        raise errors.DockPulpError('Timed out waiting for tasks %s' % awaited)

def split_content_url(url):
    i = url.find('/content')
    return url[:i], url[i:]

def setup_logger(log):
    log.setLevel(logging.INFO)
    logging.basicConfig(stream=sys.stdout, format='%(levelname)-9s %(message)s')
    return log
