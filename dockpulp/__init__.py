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
import hashlib
import logging
import os
import pprint
import re
import requests
import shutil
import sys
import tarfile
import tempfile
import time
import warnings
from contextlib import closing
from urlparse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import multiprocessing

try:
    # Python 2.6 and earlier
    import simplejson as json
except ImportError:
    if sys.version_info[0] > 2 or sys.version_info[1] > 6:
        import json
    else:
        # json on python 2.6 does not behave like simplejson
        raise

import errors
import imgutils

__version__ = "1.43"

SIG_TYPE = 'iso'
V2_C_TYPE = 'docker_manifest'
V2_BLOB = 'docker_blob'
V2_TAG = 'docker_tag'
V1_C_TYPE = 'docker_image'         # pulp content type identifier for docker
HIDDEN = 'redhat-everything'    # ID of a "hidden" repository for RCM
SIGSTORE = 'redhat-sigstore'    # ID of an iso repo for docker manifest signatures
DEFAULT_CONFIG_FILE = '/etc/dockpulp.conf'
DEFAULT_DISTRIBUTORS_FILE = '/etc/dockpulpdistributors.json'
DEFAULT_DISTRIBUTIONS_FILE = '/etc/dockpulpdistributions.json'
PREFIX = 'redhat-'


# Setup our logger
# Null logger to avoid spurious messages, add a handler in app code
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


# This is our log object, clients of this library can use this object to
# define their own logging needs
log = logging.getLogger("dockpulp")
log.setLevel(logging.INFO)

# Add the null handler
h = NullHandler()
log.addHandler(h)


class RequestsHttpCaller(object):
    def __init__(self, url, retries=0):
        self.url = url
        self.retries = retries
        self.certificate = None
        self.key = None
        self.verify = False

    def set_cert_key_paths(self, cert_path, key_path):
        self.certificate = cert_path
        self.key = key_path

    def requests_retry_session(self, session=None):
        session = session or requests.Session()
        retry = Retry(total=self.retries, read=self.retries, connect=self.retries,
                      backoff_factor=2, status_forcelist=(500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _error(self, code, url):
        """Format a nice error message."""
        raise errors.DockPulpError('Received response %s from %s' % (code, url))

    def __call__(self, meth, api, **kwargs):
        """Post an http request to a Pulp API."""
        log.debug('remote host is %s' % self.url)
        c = getattr(self.requests_retry_session(), meth)
        url = self.url + api
        if self.certificate:
            kwargs['cert'] = (self.certificate, self.key)
        kwargs['verify'] = self.verify
        log.debug('calling %s on %s' % (meth, url))
        if 'uploads' not in api:
            # prevent printing for uploads, since that will print megabytes of
            # text to the screen uselessly
            log.debug('kwargs: %s' % kwargs)
        try:
            with warnings.catch_warnings():
                # XXX: hides a known SecurityWarning (and potentially others)
                if not self.verify:
                    warnings.simplefilter("ignore")
                answer = c(url, **kwargs)

        except requests.exceptions.SSLError:
            if not self.verify:
                raise errors.DockPulpLoginError(
                    'Expired or bad certificate, please re-login')
            else:
                raise errors.DockPulpLoginError(
                    'Expired or bad certificate, or SSL verification failed')
        if 'stream' in kwargs and kwargs['stream']:
            return answer
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


class Crane(object):
    def __init__(self, pulp, cert=None, key=None):
        self.p = pulp
        self.cert = cert
        self.key = key

    def confirm(self, repos, v1=True, v2=True, silent=True, check_layers=False):

        auto = 'auto'

        if not v1 and not v2:
            v1 = True
            v2 = auto  # auto, based on /v2/ response from crane

        repos = self.p.listRepos(repos=repos, content=True)
        errors = 0
        errorids = {}
        repoids = {}
        for repo in repos:
            log.info('Testing %s' % repo['id'])
            repoids[repo['id']] = {}
            errorids[repo['id']] = False
            if repo['id'] == SIGSTORE:
                response = self._test_sigstore(repo['sigstore'])
                if silent:
                    repoids[repo['id']].update(response)
                    if response['error']:
                        errorids[repo['id']] = True
                elif response['error']:
                    errors += 1
                continue
            imgs = repo['images'].keys()
            manifests = repo['manifests'].keys()
            blobs = []
            tags = []
            for manifest in manifests:
                blobs.extend(repo['manifests'][manifest]['layers'])
                tags.append(repo['manifests'][manifest]['tag'])
            # reduce duplicate blobs
            blobs = list(set(blobs))
            if v1:
                response = self._test_repo(repo['docker-id'], repo['redirect'], imgs,
                                           repo['protected'], silent)
                if silent:
                    repoids[repo['id']].update(response)
                    if response['error']:
                        errorids[repo['id']] = True
                elif response['error']:
                    errors += 1
            if v2 == auto:
                log.debug('  Checking whether v2 is supported by crane')
                v2 = requests.get(self.p.registry + '/v2/', verify=False).ok
                if v2:
                    log.debug('  /v2/ response ok, will check v2')
                else:
                    log.debug('  /v2/ response not ok, will skip v2')

            if v2:
                response = self._test_repoV2(repo['docker-id'], repo['redirect'], manifests, blobs,
                                             tags, repo['protected'], silent)
                if silent:
                    repoids[repo['id']].update(response)
                    if errorids[repo['id']]:
                        repoids[repo['id']]['error'] = True
                elif response['error']:
                    errors += 1

            if check_layers:
                log.info('Testing each layer/blob in %s' % repo['id'])
                log.info('This may take significant machine time and resources')
                if v1:
                    response = self.p.checkLayers(repo['id'], imgs)
                    if silent:
                        repoids[repo['id']].update(response)
                        if errorids[repo['id']]:
                            repoids[repo['id']]['error'] = True
                    elif response['error']:
                        errors += 1

                if v2:
                    response = self.p.checkBlobs(repo['id'], blobs)
                    if silent:
                        repoids[repo['id']].update(response)
                        if errorids[repo['id']]:
                            repoids[repo['id']]['error'] = True
                    elif response['error']:
                        errors += 1

        repoids['numerrors'] = errors
        return repoids

    def _test_repo(self, dockerid, redirect, pulp_imgs, protected=False, silent=False):
        """Confirm we can reach crane and get data back from it."""
        # manual: curl -k https://registry.access.stage.redhat.com/v1/repositories/rhel6/rhel/images
        #         curl -k https://registry.access.stage.redhat.com/v1/repositories/rhel6.6/images
        result = {}
        result['error'] = False
        if not pulp_imgs:
            log.info('  No v1 content to test')
            return result
        url = self.p.registry + '/v1/repositories/' + dockerid + '/images'
        log.info('  Testing Pulp and Crane data')
        log.debug('  contacting %s', url)
        if protected:
            log.info('  Repo is protected, trying certs')
            answer = requests.get(url, verify=False)
            if answer.status_code != requests.codes.not_found:
                log.warning('  Crane not reporting 404 - possibly unprotected?')
            if self.cert is None and self.key is None:
                log.error('  Must provide a cert to test protected repos, skipping')
                result['error'] = True
                return result

        try:
            answer = requests.get(url, verify=False, cert=(self.cert, self.key))
        except requests.exceptions.SSLError:
            log.error('  Request failed due to invalid cert or key')
            result['error'] = True
            return result

        log.debug('  crane content: %s', answer.content)
        log.debug('  status code: %s', answer.status_code)
        if answer.status_code == requests.codes.not_found:
            log.error('  Crane returned a 404')
            result['error'] = True
            return result

        response = answer.content

        try:
            j = json.loads(response)
        except ValueError:
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

        log.debug('  crane images: %s', c_imgs)
        log.debug('  pulp images: %s', p_imgs)

        if pdiff or cdiff:
            pdiff = ', '.join((p_imgs - c_imgs))
            cdiff = ', '.join((c_imgs - p_imgs))

            log.error('  Pulp images and Crane images are not the same:')
            if pdiff:
                log.error('    In Pulp but not Crane: ' + pdiff)
            if cdiff:
                log.error('    In Crane but not Pulp: ' + cdiff)
            result['error'] = True
            return result

        log.info('  Pulp and Crane data reconciled correctly, testing content')

        if not redirect:
            reponame = 'redhat-' + dockerid.replace('/', '-')
            redirect = self.p.url + '/pulp/docker/v1/' + reponame

        missing = set()
        reachable = set()
        for img in pulp_imgs:
            for ext in ('json', 'ancestry', 'layer'):
                url = redirect + '/' + img + '/' + ext
                log.debug('  reaching for %s', url)
                try:
                    req_params = {'verify': False, 'stream': True, 'cert': (self.cert, self.key)}
                    with closing(requests.get(url, **req_params)) as answer:
                        log.debug('    got back a %s', answer.status_code)
                        if answer.status_code != requests.codes.ok:
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
        if missing:
            log.error('  Could not reach images:')
            log.error('    ' + ', '.join(missing))
            result['error'] = True
            return result

        log.info('  All images are reachable, testing Crane ancestry')

        # Testing all parent images in Crane. If one is down, docker pull will fail
        craneimages = list(c_imgs)
        parents = []
        for img in craneimages:
            url = self.p.registry + '/v1/images/' + img + '/json'
            log.debug('  reaching for %s' % url)
            try:
                answer = requests.get(url, verify=False, cert=(self.cert, self.key))
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
            except ValueError:
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
            missing = set()
            imgs = parents
            parents = []
            for img in imgs:
                url = self.p.registry + '/v1/images/' + img + '/json'
                log.debug('  reaching for %s' % url)
                try:
                    answer = requests.get(url, verify=False, cert=(self.cert, self.key))
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
                except ValueError:
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

    def _test_repoV2(self, dockerid, redirect, pulp_manifests, pulp_blobs, pulp_tags,
                     protected=False, silent=False):
        """Confirm we can reach crane and get data back from it."""
        result = {}
        result['error'] = False
        if not pulp_manifests:
            log.info('  No v2 content to test')
            return result
        url = self.p.registry + '/v2/' + dockerid + '/manifests'
        log.info('  Testing Pulp and Crane manifests')
        log.debug('  contacting %s', url)
        c_manifests = set()
        if protected:
            log.info('  Repo is protected, trying certs')
            answer = requests.get(url, verify=False)
            if answer.status_code != requests.codes.not_found:
                log.warning('  Crane not reporting 404 - possibly unprotected?')
            if self.cert is None and self.key is None:
                log.error('  Must provide a cert to test protected repos, skipping')
                result['error'] = True
                return result

        result['crane_manifests_incorrectly_named'] = []
        blobs_to_test = set()
        try:
            for manifest in pulp_manifests:
                answer = requests.get(url + '/' + manifest, verify=False,
                                      cert=(self.cert, self.key))
                log.debug('  crane content: %s', answer.content)
                log.debug('  status code: %s', answer.status_code)
                if not answer.ok:
                    continue

                c_manifests.add(manifest)

                manifest_json = answer.json()

                # Find out which blobs it references
                for fs_layer in manifest_json['fsLayers']:
                    blobs_to_test.add(fs_layer['blobSum'])

                manifest_name = manifest_json['name']
                if manifest_name != dockerid:
                    log.error('  Incorrect name (%s) in manifest: %s',
                              manifest_name, manifest)
                    result['error'] = True
                    result['crane_manifests_incorrectly_named'].append(manifest)

        except requests.exceptions.SSLError:
            log.error('  Request failed due to invalid cert or key')
            result['error'] = True
            return result

        p_manifests = set(pulp_manifests)

        pdiff = p_manifests - c_manifests
        pdiff = list(pdiff)
        pdiff.sort()
        result['manifests_in_pulp_not_crane'] = pdiff

        log.debug('  crane manifests: %s', c_manifests)
        log.debug('  pulp manifests: %s', p_manifests)

        if pdiff:
            pdiff = ', '.join((p_manifests - c_manifests))
            log.error('  Pulp manifests and Crane manifests are not the same:')
            log.error('    In Pulp but not Crane: %s', pdiff)
            result['error'] = True
            return result

        result['reachable_manifests'] = pulp_manifests

        log.info('  Pulp and Crane manifests reconciled correctly, testing blobs')
        url = self.p.registry + '/v2/' + dockerid + '/blobs/'
        log.info('  Testing expected and available blobs')
        log.debug('  contacting %s', url)
        c_blobs = set()

        try:
            for blob in blobs_to_test:
                answer = requests.head(url + blob, verify=False,
                                       cert=(self.cert, self.key), allow_redirects=True)
                log.debug('  status code: %s', answer.status_code)
                if answer.ok:
                    c_blobs.add(blob)

        except requests.exceptions.SSLError:
            log.error('  Request failed due to invalid cert or key')
            result['error'] = True
            return result

        p_blobs = set(blobs_to_test)
        pdiff = p_blobs - c_blobs
        pdiff = list(pdiff)
        pdiff.sort()
        result['blobs_in_pulp_not_crane'] = pdiff

        log.debug('  available blobs: %s', c_blobs)
        log.debug('  expected blobs: %s', p_blobs)

        if pdiff:
            pdiff = ', '.join((p_blobs - c_blobs))
            log.error('  Expected blobs and available blobs are not the same:')
            log.error('    Expected but not available: ' + pdiff)
            result['error'] = True
            return result

        result['reachable_blobs'] = pulp_blobs

        log.info('  Expected and available blobs reconciled correctly, testing tags')

        url = self.p.registry + '/v2/' + dockerid + '/tags/list'
        log.info('  Testing Pulp and Crane tags')
        log.debug('  contacting %s', url)

        try:
            answer = requests.get(url, verify=False, cert=(self.cert, self.key))
        except requests.exceptions.SSLError:
            log.error('  Request failed due to invalid cert or key')
            result['error'] = True
            return result

        log.debug('  crane content: %s', answer.content)
        log.debug('  status code: %s', answer.status_code)
        if not answer.ok:
            log.error('  Crane returned error')
            result['error'] = True
            return result

        response = answer.content

        try:
            j = json.loads(response)
        except ValueError:
            log.error('  Crane did not return tag information')
            result['error'] = True
            return result

        if j['name'] != dockerid:
            log.error('  Crane returned tag information for wrong repository')
            result['error'] = True
            return result

        p_tags = set(pulp_tags)
        c_tags = set(j['tags'])

        pdiff = p_tags - c_tags
        cdiff = c_tags - p_tags
        pdiff = list(pdiff)
        pdiff.sort()
        cdiff = list(cdiff)
        cdiff.sort()
        result['tags_in_pulp_not_crane'] = pdiff
        result['tags_in_crane_not_pulp'] = cdiff

        log.debug('  crane tags: %s', c_tags)
        log.debug('  pulp tags: %s', p_tags)

        if pdiff or cdiff:
            pdiff = ', '.join((p_tags - c_tags))
            cdiff = ', '.join((c_tags - p_tags))

            log.error('  Pulp tags and Crane tags are not the same:')
            if pdiff:
                log.error('    In Pulp but not Crane: ' + pdiff)
            if cdiff:
                log.error('    In Crane but not Pulp: ' + cdiff)
            result['error'] = True
            return result

        result['reachable_tags'] = pulp_tags

        log.info('  Pulp and Crane tags reconciled correctly, all content reachable')

        return result

    def _test_sigstore(self, signatures):
        """Confirm we can reach CDN and get data back from it."""
        result = {'error': False, 'sigs_in_pulp_not_crane': [], 'sigs_in_crane_not_pulp': []}
        if not signatures:
            log.info('  No signatures to test')
            return result
        url = self.p.cdnhost + '/content/sigstore/'
        log.info('  Confirming CDN has signatures available')
        for signature in signatures:
            log.debug('  contacting %s', url + signature)
            answer = requests.get(url + signature, verify=False)
            log.debug('  status code: %s', answer.status_code)
            if not answer.ok:
                log.error('  Signature missing in CDN: %s', signature)
                result['error'] = True
                result['sigs_in_pulp_not_crane'].append(signature)
        log.info('  Confirming CDN signatures match Pulp')
        log.debug('  contacting %s', url + 'PULP_MANIFEST')
        answer = requests.get(url + 'PULP_MANIFEST', verify=False)
        if not answer.ok:
            log.error('  Pulp Manifest missing in CDN')
            result['error'] = True
            return result
        csigs = answer.text.split('\n')
        for csig in csigs:
            sig = csig.split(',')[0]
            if sig and sig not in signatures:
                log.error('  Signature in CDN but not pulp: %s', sig)
                result['error'] = True
                result['sigs_in_crane_not_pulp'].append(sig)
        return result


class Pulp(object):
    #                           section, process function, target attribute
    MANDATORY_CONF_SECTIONS = (('pulps', "_set_env_attr", "url"),
                               ('registries', "_set_env_attr", "registry"),
                               ('filers', "_set_env_attr", "cdnhost"),
                               ('redirect', "_set_bool", "redirect"),
                               ('distributors', "_set_env_attr", "distributors"),
                               ('release_order', "_set_env_attr", "release_order"))
    OPTIONAL_CONF_SECTIONS = (('certificates', "_set_cert", None),
                              ('chunk_size', "_set_int_attr", "chunk_size"),
                              ('timeout', "_set_int_attr", "timeout"),
                              ('retries', "_set_int_attr", "retries"),
                              ('distribution', "_set_bool", "dists"),
                              ('signatures', "_set_independent_attr", "sigs"))
    AUTH_CER_FILE = "pulp-%s.cer"
    AUTH_KEY_FILE = "pulp-%s.key"

    def __init__(self, env='qa', config_file=DEFAULT_CONFIG_FILE,
                 config_override=None, config_distributors=DEFAULT_DISTRIBUTORS_FILE,
                 config_distributions=DEFAULT_DISTRIBUTIONS_FILE):
        """Construct a Pulp class.

        The constructor sets up the remote hostname given an environment.
        Accepts shorthand, or full hostnames.
        """
        self.certificate = None  # set in login()
        self.key = None
        self.env = env
        self.name_enforce = {}
        self.load_configuration(config_file)
        self._load_override_conf(config_override)
        try:
            self.retries
        except AttributeError:
            self.retries = 1
        if self.retries is None or self.retries < 1:
            self.retries = 1
        self._request = RequestsHttpCaller(self.url, self.retries)
        self._request.set_cert_key_paths(self.certificate, self.key)
        if not os.path.exists(config_distributors):
                log.error('could not load distributors json: %s' % config_distributors)
        self.distributorconf = json.load(open(config_distributors, 'r'))
        if not os.path.exists(config_distributions):
                log.error('could not load distributions json: %s' % config_distributions)
        self.distributionconf = json.load(open(config_distributions, 'r'))
        try:
            self.timeout
        except AttributeError:
            self.timeout = 180
        if self.timeout is None:
            self.timeout = 180
        try:
            self.dists
        except AttributeError:
            self.dists = False

    def _set_bool(self, attrs):
        for key, boolean in attrs:
            if self.env == key:
                if boolean == "yes":
                    return True
                elif boolean == "no":
                    return False
        raise errors.DockPulpConfigError('Redirect and Distribution must be \'yes\' or \'no\'')

    def _set_cert(self, attrs):
        for key, cert_path in attrs:
            if self.env == key:
                self.certificate = os.path.join(os.path.expanduser(cert_path),
                                                self.AUTH_CER_FILE % self.env)
                self.key = os.path.join(os.path.expanduser(cert_path),
                                        self.AUTH_KEY_FILE % self.env)

    def _set_independent_attr(self, attrs):
        # set environment independent attributes
        return dict(attrs)

    def _set_env_attr(self, attrs):
        for key, val in attrs:
            if self.env == key:
                return val
        return None

    def _set_int_attr(self, attrs):
        for key, val in attrs:
            if self.env == key:
                try:
                    return int(val)
                except TypeError:
                    pass
        return None

    def _load_override_conf(self, config_override):
        if not isinstance(config_override, dict):
            return
        for sections in (self.MANDATORY_CONF_SECTIONS,
                         self.OPTIONAL_CONF_SECTIONS):
            for key, process, target in sections:
                if key in config_override:
                    process_f = getattr(self, process)
                    ret = process_f([(self.env, config_override[key])])
                    if target:
                        setattr(self, target, ret)

    def _cleanup(self, creddir):
        """Clean up the session cert and key.

        Called automatically on program exit
        """
        log.debug('cleaning up session credentials')
        shutil.rmtree(creddir, ignore_errors=True)

    def _createUploadRequest(self):
        """Create an upload request."""
        log.debug('creating upload request')
        rid = self._post('/pulp/api/v2/content/uploads/')['upload_id']
        log.info('upload request: %s' % rid)
        return rid

    def _deleteUploadRequest(self, rid):
        """Delete an upload request."""
        log.debug('deleting upload request since we are done')
        self._delete('/pulp/api/v2/content/uploads/%s/' % rid)
        log.info('removed upload request %s' % rid)

    def _error(self, code, url):
        """Format a nice error message."""
        raise errors.DockPulpError('Received response %s from %s' % (code, url))

    def _getRepo(self, env, config_file=DEFAULT_CONFIG_FILE):
        """Set up hostname for sync."""
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

        self.syncenv = conf.get('registries', env)

    def _getTags(self, repo):
        """Return the tag list for a given repo."""
        log.debug('getting tag data...')
        params = {'details': True}
        rinfo = self._get('/pulp/api/v2/repositories/%s/' % repo,
                          params=params)
        if 'tags' in rinfo['scratchpad']:
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

    def associate(self, dist_id, repo):
        """Associate a distributor with a repo."""
        try:
            data = self.distributorconf[dist_id]
        except KeyError:
            raise errors.DockPulpConfigError(
                'Distributor %s not listed in dockpulpdistributors.json' % dist_id)

        log.debug(data)

        result = self._post('/pulp/api/v2/repositories/%s/distributors/' % repo,
                            data=json.dumps(data))
        return result

    def checkLayers(self, repo, images):
        response = {}
        response['failedlayers'] = []
        response['error'] = False
        for img in images:
            layer_url = '/pulp/docker/v1/%s/%s/layer' % (repo, img)
            try:
                r = self._get(layer_url, stream=True)
            except requests.exceptions.ConnectionError:
                log.warning('Layer %s not available in pulp for repo %s' % (img, repo))
                response['failedlayers'].append(img)
                response['error'] = True
                continue
            try:
                tar = tarfile.open(fileobj=r.raw, mode='r|*')
                tar.close()
            except IOError:
                log.warning('Layer %s corrupted for repo %s' % (img, repo))
                response['failedlayers'].append(img)
                response['error'] = True

        return response

    def checkBlobs(self, repo, blobs):
        response = {}
        response['failedblobs'] = []
        response['error'] = False
        for blob in blobs:
            blob_url = '/pulp/docker/v2/%s/blobs/%s' % (repo, blob)
            try:
                r = self._get(blob_url, stream=True)
            except requests.exceptions.ConnectionError:
                log.warning('Blob %s not available in pulp for repo %s' % (blob, repo))
                response['failedblobs'].append(blob)
                response['error'] = True
                continue
            sig = hashlib.sha256(r.raw.read())
            shasum = 'sha256:%s' % sig.hexdigest()
            if shasum != blob:
                log.warning('Blob %s does not have expected shasum %s' % (blob, shasum))
                response['failedblobs'].append(blob)
                response['error'] = True
        return response

    def cleanOrphans(self, content_type=V1_C_TYPE):
        """Remove orphaned docker content of given type."""
        log.debug('Removing docker orphans not implemented in Pulp 2.4')
        tid = self._delete('/pulp/api/v2/content/orphans/%s/' % content_type)
        self.watch(tid)

    def cleanUploadRequests(self):
        """Remove outstanding upload requests from Pulp to reclaim space."""
        uploads = self.listUploadRequests()
        for upload in uploads:
            self._deleteUploadRequest(upload)

    def copy(self, drepo, img, source=HIDDEN):
        """Copy an image from one repo to another."""
        if img.startswith("sha256:"):

            data = {
                'source_repo_id': source,
                'criteria': {
                    'type_ids': [V2_C_TYPE, V2_BLOB, V2_TAG],
                    'filters': {
                        'unit': {
                            "$or": [{'digest': img}, {'manifest_digest': img}]
                        }
                    }
                },
                'override_config': {}
            }

        else:

            data = {
                'source_repo_id': source,
                'criteria': {
                    'type_ids': [V1_C_TYPE],
                    'filters': {
                        'unit': {
                            'image_id': img
                        }
                    }
                },
                'override_config': {}
            }

        log.debug('copy request we are sending:')
        log.debug(pprint.pformat(data))
        log.info('copying %s from %s to %s' % (img, source, drepo))
        tid = self._post(
            '/pulp/api/v2/repositories/%s/actions/associate/' % drepo,
            data=json.dumps(data))
        self.watch(tid)

    def copy_filters(self, drepo, source=HIDDEN, filters={}, v1=True, v2=True):
        """Copy an contnet from one repo to another according to filters."""
        type_ids = []
        if v1:
            type_ids.append(V1_C_TYPE)
        if v2:
            type_ids.extend([V2_C_TYPE, V2_BLOB, V2_TAG])
        data = {
            'source_repo_id': source,
            'criteria': {
                'type_ids': type_ids,
                'filters': filters,
            },
            'override_config': {}
        }
        log.debug('copy request we are sending:')
        log.debug(pprint.pformat(data))
        log.info('copying from %s to %s' % (source, drepo))
        tid = self._post(
            '/pulp/api/v2/repositories/%s/actions/associate/' % drepo,
            data=json.dumps(data))
        self.watch(tid)

    def crane(self, repos=[], wait=True, skip=False, force_refresh=False):
        """Export pulp configuration to crane for one or more repositories."""
        if len(repos) == 0:
            repos = self.getAllRepoIDs()
        tasks = []
        results = []

        if not wait:
            pool = multiprocessing.Pool()

        for repo in repos:
            releasekeys = self.release_order.strip().split(",")
            distributors = []
            for key in releasekeys:
                distributors.append(self.distributorconf[key])
            for distributor in distributors:
                dist_id = distributor['distributor_id']
                override = {}
                try:
                    override = distributor['override_config']
                except KeyError:
                    pass

                if skip:
                    override['skip_fast_forward'] = skip
                if force_refresh:
                    override['force_refresh'] = force_refresh
                log.info('updating distributor: %s' % dist_id)
                url = '/pulp/api/v2/repositories/%s/actions/publish/' % repo
                kwds = {"data": json.dumps({'id': dist_id, 'override_config': override})}
                log.debug('sending %s' % kwds)
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

    def createRepo(self, repo_id, url, registry_id=None, desc=None, title=None, protected=False,
                   distributors=True, prefix_with=PREFIX, productline=None, library=False,
                   distribution=None, repotype=None, importer_type_id=None, rel_url=None):
        """Create a docker repository in pulp.

        id and description are required
        """
        if not repo_id.startswith(prefix_with):
            repo_id = prefix_with + repo_id
        if '/' in repo_id:
            log.warning('Looks like you supplied a docker repo ID, not pulp')
            raise errors.DockPulpError('Pulp repo ID cannot have a "/"')
        if registry_id is None:
            if productline:
                pindex = repo_id.find(productline)
                registry_id = productline + '/' + repo_id[pindex + len(productline) + 1:]
            elif library:
                registry_id = repo_id.replace(prefix_with, '')
            else:
                registry_id = repo_id.replace(prefix_with, '').replace('-', '/', 1)

        rurl = url
        if url and url.startswith('http'):
            # want to strip off hostname info here
            url = urlparse(url).path
        if rurl and not rurl.startswith('http'):
            rurl = self.cdnhost + url
        if not desc:
            desc = 'No description'
        if not title:
            title = repo_id
        log.info('creating repo %s' % repo_id)
        log.info('docker ID is %s' % registry_id)
        if rurl:
            log.info('redirect is %s' % rurl)
        stuff = {
            'id': repo_id,
            'description': desc,
            'display_name': title,
            'importer_type_id': 'docker_importer',
            'importer_config': {},
            'notes': {'_repo-type': 'docker-repo'},
        }
        if rel_url:
            stuff['notes']['relative_url'] = rel_url
        if distribution:
            try:
                distconf = self.distributionconf[distribution]
            except KeyError:
                raise errors.DockPulpConfigError("Distribution %s not defined in %s" %
                                                 (distribution, DEFAULT_DISTRIBUTIONS_FILE))
            if productline:
                if not productline.endswith(distconf.get('name_enforce', '')):
                    raise errors.DockPulpError("%s is a %s repo, product-line must end with %s" %
                                               (repo_id, distribution, distconf['name_enforce']))
                for restrict in distconf['name_restrict']:
                    if restrict in productline:
                        raise errors.DockPulpError(
                            "%s is a %s repo, product-line must not contain %s" %
                            (repo_id, distribution, restrict))
            # library level repo do not use product-line
            elif library:
                if not repo_id.endswith(distconf.get('name_enforce', '')):
                    raise errors.DockPulpError("%s is a %s repo, repo id must end with %s" %
                                               (repo_id, distribution, distconf['name_enforce']))
                for restrict in distconf['name_restrict']:
                    if restrict in repo_id:
                        raise errors.DockPulpError("%s is a %s repo, repo id must not contain %s" %
                                                   (repo_id, distribution, restrict))
            try:
                if not url.startswith(distconf.get('content_enforce', '')):
                    raise errors.DockPulpError("%s is a %s repo, content-url must start with %s" %
                                               (repo_id, distribution, distconf['content_enforce']))
            except AttributeError:
                pass
            if distconf['signature'] != "":
                sig = self.getSignature(distconf['signature'])
                stuff['notes']['signatures'] = sig
            stuff['notes']['distribution'] = distribution
        elif self.dists and repo_id != HIDDEN and repo_id != SIGSTORE:
            raise errors.DockPulpError("Env %s requires distribution defined at repo creation" %
                                       self.env)
        if repotype:
            stuff['notes']['_repo-type'] = repotype
        if importer_type_id:
            stuff['importer_type_id'] = importer_type_id
        if self.distributors == "":
            distributors = False
        if distributors:
            stuff['distributors'] = []
            distributorkeys = self.distributors.strip().split(",")
            for key in distributorkeys:
                stuff['distributors'].append(self.distributorconf[key])
            for distributor in stuff['distributors']:
                try:
                    if distributor['distributor_type_id'] == 'docker_distributor_web':
                        distributor['distributor_config']['protected'] = protected
                        distributor['distributor_config']['repo-registry-id'] = registry_id
                        distributor['distributor_config']['redirect-url'] = rurl
                except KeyError:
                    continue
        else:
            stuff['distributors'] = []
        log.debug('data sent in request:')
        log.debug(pprint.pformat(stuff))
        self._post('/pulp/api/v2/repositories/', data=json.dumps(stuff))
        return stuff

    def deleteRepo(self, id):
        """Delete a repository; cannot be undone!."""
        log.info('deleting repo: %s' % id)
        tid = self._delete('/pulp/api/v2/repositories/%s/' % id)
        self.watch(tid)

    def disassociate(self, dist_id, repo):
        """Disassociate a distributor associated with a repo."""
        tid = self._delete('/pulp/api/v2/repositories/%s/distributors/%s/' % (repo, dist_id))
        self.watch(tid)

    def dump(self, pretty=False):
        """Dump the complete configuration of an environment to json format."""
        if pretty:
            return json.dumps(self.listRepos(content=True),
                              sort_keys=True, indent=2)
        else:
            return json.dumps(self.listRepos(content=True))

    def exists(self, rid):
        """Return True if a repository already exists, False otherwise."""
        data = {
            'criteria': {
                'filters': {
                    'id': rid,
                }
            },
            'fields': ['id']
        }
        found = self._post('/pulp/api/v2/repositories/search/',
                           data=json.dumps(data))
        return len(found) > 0

    def getAllRepoIDs(self):
        """Get all repository IDs in Pulp."""
        repos = []
        log.info('getting all repositories...')
        params = {'details': True}
        for blob in self._get('/pulp/api/v2/repositories/', params=params):
            repos.append(blob['id'])
        repos.sort()
        repos.remove(HIDDEN)  # remove the RCM-internal repository
        return repos

    def getAncestors(self, iid, parents=[]):
        """Return the list of layers (ancestors) of a given image."""
        # a rest call is made per parent, which impacts performance greatly
        data = {
            'criteria': {
                'filters': {
                    'unit': {
                        'image_id': iid
                    }
                },
                'limit': 1,
            },
        }
        log.debug('search request:')
        log.debug(json.dumps(data))
        try:
            img = self._post('/pulp/api/v2/repositories/%s/search/units/' % HIDDEN,
                             data=json.dumps(data))[0]
        except IndexError:
            log.info('missing parent layer %s', iid)
            log.info('skipping layer')
            return parents
        img['metadata'].setdefault('parent_id', None)
        par = img['metadata']['parent_id']
        if par is not None:
            parents.append(par)
            return self.getAncestors(par, parents=parents)
        else:
            return parents

    def getDistributionSig(self, dist):
        """Get distribution signature."""
        # No longer used, keeping for unit tests
        return self.distributionconf[dist]['signature']

    def getImageIdsExist(self, iids=[]):
        """Return a list of layers already uploaded to the server."""
        data = json.dumps({
            'criteria': {
                'filters': {
                    'unit': {
                        'image_id': {"$in": iids}
                    }
                },
            },
        })
        log.debug('checking imageids %s', ', '.join(iids))
        log.debug(data)
        result = self._post('/pulp/api/v2/repositories/%s/search/units/' % HIDDEN, data=data)
        log.debug(result)
        return [c['metadata']['image_id'] for c in result]

    def getPrefix(self):
        """Return repository prefix."""
        return PREFIX

    def getRepos(self, rids, fields=None):
        """Return list of repo objects with given IDs."""
        data = {
            "criteria": {
                "filters": {
                    "id": {"$in": rids}
                }
            }
        }

        if fields:
            data["fields"] = fields

        log.debug('getting repositories %s', ', '.join(rids))
        return self._post('/pulp/api/v2/repositories/search/',
                          data=json.dumps(data))

    def getSignature(self, sig):
        """Return a signature key."""
        try:
            self.sigs
        except AttributeError:
            raise errors.DockPulpConfigError('Signatures not defined in dockpulp.conf')
        try:
            return self.sigs[sig]
        except KeyError:
            log.error('Signature not defined in dockpulp.conf')
            raise errors.DockPulpConfigError(
                'Available signatures are: %s' % ', '.join(self.sigs.keys()))

    def getSigstore(self):
        """Return the sigstore repo id."""
        return SIGSTORE

    def getTask(self, tid):
        """Return a task report for a given id."""
        log.debug('getting task %s information' % tid)
        return self._get('/pulp/api/v2/tasks/%s/' % tid)

    def deleteTask(self, tid):
        """Delete a task with the given id."""
        log.debug('deleting task: %s' % tid)
        return self._delete('/pulp/api/v2/tasks/%s/' % tid)

    def getTasks(self, tids):
        """Return a task report for a given id."""
        log.debug('getting tasks %s information' % tids)
        criteria = json.dumps({
            "criteria": {
                "filters": {
                    "task_id": {
                        "$in": tids,
                    }
                }
            }
        })
        return self._post('/pulp/api/v2/tasks/search/', data=criteria)

    def isRedirect(self):
        return self.redirect

    def listOrphans(self, content_type=V1_C_TYPE):
        """Return a list of orphaned content of given type."""
        log.debug('getting list of orphaned %s' % content_type)
        return self._get('/pulp/api/v2/content/orphans/%s/' % content_type)

    def listRepos(self, repos=None, content=False, history=False, labels=False):
        """Return information about pulp repositories.

        If repos is a string or list of strings, treat them as repo IDs
        and get information about each one. If None, get all repos.
        """
        blobs = []
        params = {'details': True}
        if not repos:
            # get all repository IDs first since none were specified
            repos = self.getAllRepoIDs()
        if not isinstance(repos, list):
            assert isinstance(repos, str) or isinstance(repos, unicode)
            repos = [repos]
        # return information for each repo
        for repo in repos:
            blobs.append(self._get('/pulp/api/v2/repositories/%s/' % repo,
                                   params=params))
        clean = []
        # From here we trim out data nobody cares about
        # we assume distributors have the same configuration
        for blob in blobs:
            if blob['notes']['_repo-type'] != 'docker-repo' and blob['id'] != SIGSTORE:
                raise errors.DockPulpError('Non-docker repo hit, what should I do?!')
            r = {
                'id': blob['id'],
                'description': blob['description'],
                'title': blob['display_name'],
            }

            try:
                if len(blob['distributors']) > 0:
                    for distributor in blob['distributors']:
                        if distributor['distributor_type_id'] == 'docker_distributor_web':
                            r['protected'] = distributor['config']['protected']
                            r['docker-id'] = distributor['config']['repo-registry-id']
                            break
            except KeyError:
                log.debug("ignoring repo-id %s, incomplete distributor config",
                          r['id'])
                continue

            if blob['distributors']:
                try:
                    for distributor in blob['distributors']:
                        if distributor['distributor_type_id'] == 'docker_distributor_web':
                            r['redirect'] = distributor['config']['redirect-url']
                            break
                except KeyError:
                    log.debug("no redirect for repo-id %s, using pulp defaults",
                              r['id'])
                    r['redirect'] = None
            else:
                r['redirect'] = None

            if blob['distributors']:
                dists = []
                for distributor in blob['distributors']:
                    dists.append(distributor['id'])
                r['distributors'] = ', '.join(dists)

            else:
                r['distributors'] = None

            try:
                r['signatures'] = blob['notes']['signatures']
            except KeyError:
                log.debug("no signature for repo-id %s", r['id'])

            try:
                r['distribution'] = blob['notes']['distribution']
            except KeyError:
                log.debug("no distribution for repo-id %s", r['id'])

            if content or history:
                # Fetch all content in a single request
                data = {
                    'criteria': {
                        'type_ids': [V1_C_TYPE, V2_C_TYPE, V2_BLOB, V2_TAG, SIG_TYPE],
                        'filters': {
                            'unit': {}
                        }
                    }
                }
                log.debug('getting unit information with request:')
                log.debug(pprint.pformat(data))
                units = self._post(
                    '/pulp/api/v2/repositories/%s/search/units/' % blob['id'],
                    data=json.dumps(data))
                if blob['id'] == SIGSTORE:
                    r['sigstore'] = []
                    sigs = [unit for unit in units
                            if unit['unit_type_id'] == SIG_TYPE]
                    for sig in sigs:
                        r['sigstore'].append(sig['metadata']['name'])
                    clean.append(r)
                    clean.sort()
                    continue
                r['images'] = {}
                if labels:
                    r['v1_labels'] = {}
                imgs = [unit for unit in units
                        if unit['unit_type_id'] == V1_C_TYPE]
                for img in imgs:
                    r['images'][img['metadata']['image_id']] = []

                    if labels:
                        labels = self._get('/pulp/docker/v1/%s/%s/json' %
                                           (blob['id'], img['metadata']['image_id']))
                        try:
                            r['v1_labels'][img['metadata']['image_id']] = labels['config']['Labels']
                        except KeyError:
                            r['v1_labels'][img['metadata']['image_id']] = None

                if 'tags' in blob['scratchpad']:
                    tags = blob['scratchpad']['tags']
                    for tag in tags:
                        try:
                            r['images'][tag['image_id']].append(tag['tag'])
                            r['images'][tag['image_id']].sort()
                        except KeyError:
                            log.warning('stale scratch pad data found!')
                            log.warning(
                                '%s here but not in repo!' % tag['image_id'])
                manifests = [unit for unit in units
                             if unit['unit_type_id'] == V2_C_TYPE]

                v2_blobs = {}  # digest -> seen reference?
                for unit in units:
                    if unit['unit_type_id'] == V2_BLOB:
                        v2_blobs[unit['metadata']['digest']] = False

                tags = [unit for unit in units
                        if unit['unit_type_id'] == V2_TAG]

                r['manifests'] = {}
                for manifest in manifests:
                    fs_layers = manifest['metadata']['fs_layers']
                    layers = []
                    for layer in fs_layers:
                        blob_sum = layer['blob_sum']
                        if blob_sum in v2_blobs:
                            v2_blobs[blob_sum] = True
                            layers.append(blob_sum)
                        else:
                            log.warning('manifest %s references blob %s '
                                        'but this is not present',
                                        manifest['metadata']['digest'],
                                        blob_sum)

                    digest = manifest['metadata']['digest']
                    r['manifests'][digest] = {}
                    tag = None
                    if 'tag' not in manifest['metadata'].keys():
                        for tag_dict in tags:
                            if tag_dict['metadata']['manifest_digest'] == digest:
                                tag = tag_dict['metadata']['name']
                                break
                    else:
                        tag = manifest['metadata']['tag']
                    r['manifests'][digest]['tag'] = tag
                    r['manifests'][digest]['layers'] = layers

                for v2_blob, seen_ref in v2_blobs.items():
                    if not seen_ref:
                        log.warning("unreferenced blob present: %s", v2_blob)

                r['tags'] = {}
                for tag in tags:
                    r['tags'][tag['metadata']['name']] = tag['metadata']['manifest_digest']

                if history:
                    if r['id'] == HIDDEN:
                        log.warning("Hidden repo does not have history info, skipping")
                        clean.append(r)
                        clean.sort()
                        continue
                    for manifest in r['manifests'].keys():
                        try:
                            data = self._get('/pulp/docker/v2/%s/manifests/%s' % (
                                blob['id'], manifest))
                        except errors.DockPulpError:
                            log.warning("Manifest unreachable, skipping %s", manifest)
                            r['manifests'][manifest]['v1parent'] = None
                            r['manifests'][manifest]['v1id'] = None
                            r['manifests'][manifest]['v1labels'] = None
                            continue

                        # Unsure if all v2 images will have v1 history
                        try:
                            hist = json.loads(data['history'][0]['v1Compatibility'])
                        except KeyError:
                            log.debug("%s has no v1 history information, skipping", manifest)
                            r['manifests'][manifest]['v1parent'] = None
                            r['manifests'][manifest]['v1id'] = None
                            r['manifests'][manifest]['v1labels'] = None
                            continue

                        try:
                            r['manifests'][manifest]['v1parent'] = hist['parent']
                        except KeyError:
                            log.debug("%s has no v1 history parent information", manifest)
                            r['manifests'][manifest]['v1parent'] = None

                        try:
                            r['manifests'][manifest]['v1id'] = hist['id']
                        except KeyError:
                            log.debug("%s has no v1 history id information", manifest)
                            r['manifests'][manifest]['v1id'] = None

                        try:
                            r['manifests'][manifest]['v1labels'] = hist['config']['Labels']
                        except KeyError:
                            log.debug("%s has no v1 label information", manifest)
                            r['manifests'][manifest]['v1labels'] = None

            clean.append(r)
            clean.sort()
        return clean

    def listUploadRequests(self):
        """Return a pending upload requests."""
        log.debug('getting all upload IDs')
        return self._get('/pulp/api/v2/content/uploads/')['upload_ids']

    def load_configuration(self, conf_file):
        conf = ConfigParser.ConfigParser()
        if not conf_file:
            raise errors.DockPulpConfigError('Missing config file')
        conf.readfp(open(conf_file))
        for sect, process, target in self.MANDATORY_CONF_SECTIONS:
            if not conf.has_section(sect):
                raise errors.DockPulpConfigError('Missing section: %s' % sect)
            if not conf.has_option(sect, self.env):
                raise errors.DockPulpConfigError('%s section is missing %s' %
                                                 (sect, self.env))
            process_f = getattr(self, process)
            ret = process_f(conf.items(sect))
            if target:
                setattr(self, target, ret)

        for sect, process, target in self.OPTIONAL_CONF_SECTIONS:
            if conf.has_section(sect):
                process_f = getattr(self, process)
                ret = process_f(conf.items(sect))
                if target:
                    setattr(self, target, ret)

    def login(self, user, password):
        """Log into pulp using a user/pass combo.

        A certificate is saved for additional logins.
        """
        log.info('logging in as %s' % user)
        log.info('certificate %s' % self._request.certificate)
        if not self._request.certificate or\
           not os.path.exists(self._request.certificate):
            blob = self._post('/pulp/api/v2/actions/login/',
                              auth=(user, password))
            sessiondir = tempfile.mkdtemp()
            log.info('session info saved in %s' % sessiondir)
            for part in ('certificate', 'key'):
                # save the cert and key for future calls
                f = os.path.join(sessiondir, ('pulp-%s.' % self.env) + part[:3])
                fd = open(f, 'w')
                fd.write(blob[part])
                fd.close()
                setattr(self._request, part, f)
                setattr(self, part, f)
            atexit.register(self._cleanup, sessiondir)

    def logout(self):
        """Log out.

        Does nothing except clean up session info if necessary.
        There is no need to call this function.
        """
        log.info('logging out')
        if self._request.certificate:
            self._cleanup(os.path.dirname(self._request.certificate))

    def remove(self, repo, img):
        """Remove an image from a repo."""
        if img.startswith("sha256:"):

            data = {
                'criteria': {
                    'type_ids': [V2_C_TYPE, V2_BLOB, V2_TAG],
                    'filters': {
                        'unit': {
                            "$or": [{'digest': img}, {'manifest_digest': img}]
                        }
                    }
                },
                'limit': 1,
                'override_config': {}
            }

        else:

            data = {
                'criteria': {
                    'type_ids': [V1_C_TYPE],
                    'filters': {
                        'unit': {
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
        """Search and return Pulp repository IDs matching given pattern."""
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

    def set_certs(self, cert, key):
        self.certificate = cert
        self.key = key
        self._request.set_cert_key_paths(self.certificate, self.key)

    def setDebug(self):
        """Turn on debug output."""
        log.setLevel(logging.DEBUG)

    def syncRepo(self, env=None, repo=None, config_file=DEFAULT_CONFIG_FILE,
                 prefix_with=PREFIX, feed=None, basic_auth_username=None,
                 basic_auth_password=None, ssl_validation=None, upstream_name=None):
        """Sync repo."""
        if not repo.startswith(prefix_with):
            repo = prefix_with + repo

        repoinfo = self.listRepos(repo, True)
        if not upstream_name:
            upstream_name = repoinfo[0]['docker-id']

        if not feed:
            self._getRepo(env, config_file)
            feed = self.syncenv

        if not ssl_validation:
            ssl_validation = False

        data = {
            'override_config': {
                'ssl_validation': ssl_validation,
                'feed': feed,
                'upstream_name': upstream_name,
                'enable_v1': True,
            }
        }

        if basic_auth_username and basic_auth_password:
            data['override_config'].update({
                'basic_auth_username': basic_auth_username,
                'basic_auth_password': basic_auth_password,
            })

        log.info('Syncing from %s' % feed)
        log.info('Syncing repo %s' % repo)
        tid = self._post('/pulp/api/v2/repositories/%s/actions/sync/' % repo,
                         data=json.dumps(data))
        self.watch(tid)

        repoinfo = repoinfo[0]

        if len(repoinfo['images'].keys()) == 0:
            oldimgs = []
        else:
            oldimgs = repoinfo['images'].keys()

        if len(repoinfo['manifests'].keys()) == 0:
            oldmanifests = []
        else:
            oldmanifests = repoinfo['manifests'].keys()

        repoinfo = self.listRepos(repo, True)
        repoinfo = repoinfo[0]

        newimgs = repoinfo['images'].keys()
        imgs = list(set(newimgs) - set(oldimgs))
        imgs.sort()

        newmanifests = repoinfo['manifests'].keys()
        manifests = list(set(newmanifests) - set(oldmanifests))
        manifests.sort()

        # Need to maintain HIDDEN
        if repo != HIDDEN:
            for img in imgs:
                self.copy(HIDDEN, img, repo)
            for manifest in manifests:
                self.copy(HIDDEN, manifest, repo)

        return (imgs, manifests)

    def updateRepo(self, rid, update):
        """Update metadata on a repository.

        "update" is a dictionary of keys to update with new values
        """
        log.info('updating repo %s' % rid)
        delta = {
            'delta': {},
            'distributor_configs': {
            }
        }

        distributorkeys = []
        validdistributorkeys = []
        webdist = 'docker_distributor_web'
        exportdist = 'docker_distributor_export'

        disturl = '/pulp/api/v2/repositories/%s/distributors/' % rid
        log.debug("calling %s", disturl)
        blob = self._get(disturl)
        for did in blob:
            if did['distributor_type_id'] == webdist or did['distributor_type_id'] == exportdist:
                validdistributorkeys.append(did['id'])
            else:
                distributorkeys.append(did['id'])
        for distributorkey in validdistributorkeys:
            delta['distributor_configs'][distributorkey] = {}
        # we intentionally ignore everything else
        valid = ('redirect-url', 'protected', 'repo-registry-id', 'description', 'display_name',
                 'tag', 'signature', 'distribution')
        for u in update.keys():
            if u not in valid:
                log.warning('ignoring %s, not sure how to update' % u)
        for key in ('description', 'display_name'):
            if key in update:
                delta['delta'][key] = update[key]
        if 'tag' in update:
            tags, iid = update['tag'].split(':')
            new_tags = tags.split(",")
            existing = self._getTags(rid)  # need to preserve existing tags
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
            if key in update:
                if key == 'redirect-url':
                    if re.match("https?:\/\/.+\/.*", update[key]) is None:
                        raise errors.DockPulpError('The redirect-url must follow the form '
                                                   'http://example/url or https://example/url')
                for distributorkey in delta['distributor_configs']:
                    delta['distributor_configs'][distributorkey][key] = update[key]
        if 'signature' in update or 'distribution' in update:
            delta['delta']['notes'] = {}
        if 'signature' in update:
            sig = self.getSignature(update['signature'])
            delta['delta']['notes']['signatures'] = sig
        if 'distribution' in update:
            sig = self.distributionconf[update['distribution']]['signature']
            delta['delta']['notes']['distribution'] = update['distribution']
            if 'signature' not in update and sig != "":
                sig = self.getSignature(sig)
                delta['delta']['notes']['signatures'] = sig
        for distributorkey in distributorkeys:
            delta['distributor_configs'][distributorkey] = {}
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

        :param image: str, pathname
        """
        # TODO: support a hidden repo for "no-channel" style uploads
        rid = self._createUploadRequest()
        size = int(os.path.getsize(image))
        curr = 0
        mb = 1024 * 1024  # 1M
        try:
            block = self.chunk_size
            if block is None:
                block = mb
            # chunk size is in MB, need to convert
            else:
                block = block * mb
        except AttributeError:
            # chunk size defaults to 1 MB if not set
            block = mb
        log.info('uploading a %sM image' % (size / mb,))
        log.debug('using a chunk size of %sM' % (block / mb,))
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
            'unit_type_id': V1_C_TYPE,
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
        timer = max(self.timeout, (size / mb) * 2)  # wait 2 seconds per megabyte, or timeout,
        self.watch(tid, timeout=timer)  # whichever is greater
        self._deleteUploadRequest(rid)

    def watch(self, tid, timeout=None, poll=5):
        """Watch a task ID and return when it finishes or fails."""
        if timeout is None:
            timeout = self.timeout
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

    def is_task_successful(self, task):
        # Try to inspect task results to catch buried failures
        if task["state"] == "error":
            return False
        elif type(task["result"]) == list:
            # Used by Content Unit / Repo association
            # No buried errors found so far
            return True
        elif type(task["result"]) == dict:
            # Used by Distributors
            if 'result' in task["result"]:
                # Used by Yum distributor
                return task['result']['result'] == 'success'
            elif 'success_flag' in task["result"]:
                # Used by CDN distributor
                return task["result"]['success_flag']
            elif 'units_successful' in task["result"] or task["result"] == {}:
                return True
        elif task["state"] == "finished":
            return True
        elif task["state"] in ("error", "canceled"):
            return False
        log.info("Unknown task result type: %s (%s)" % (task['result'], type(task['result'])))
        return True

    def resolve_task_type(self, task):
        tags = task.get("tags", [])
        if "pulp:action:publish" in tags:
            repo = [tag for tag in tags if tag.startswith("pulp:repository")][0]
            repo = repo.replace("pulp:repository:", "")
            return "Publishing to %s" % repo
        elif "pulp:action:associate" in tags:
            repos = [tag for tag in tags if tag.startswith("pulp:repository")]
            repos = [repo.replace("pulp:repository:", "") for repo in repos]
            return "Association content %s -> %s" % (repos[1], repos[0])
        elif "pulp:action:import_upload" in tags:
            repo = [tag for tag in tags if tag.startswith("pulp:repository")][0]
            repo = repo.replace("pulp:repository:", "")
            return "Importing content to repo %s" % (repo)

    def watch_tasks(self, task_ids, timeout=None, poll=5):
        """Wait for all supplied task ids to complete.

        Doesn't wait for other tasks if at least one fails,
        just cancel everything running and raise error.
        """
        running = set(task_ids)
        running_count = len(running)
        failed = False
        results = {}
        failed_tasks = []

        if timeout is None:
            timeout = self.timeout
        if running:
            log.debug("Waiting on the following %d Pulp tasks: %s" % (
                len(running), ",".join(sorted(running))))
        while running:
            time.sleep(poll)
            tasks_found = self.getTasks(list(running))
            finished = [t for t in tasks_found if t["state"] in ("finished", "error", "canceled")]
            for t in finished:
                if self.is_task_successful(t):
                    log.debug("Task successful: %s, %s" % (t["task_id"], self.resolve_task_type(t)))
                else:
                    log.debug("Finished: Failed: %s" % (t))
                results[t["task_id"]] = t
            # some tasks could be already removed from cache - search_tasks
            # doesn't find them. Need check manually
            for task_id in set(running) - set([t["task_id"] for t in tasks_found]):
                task = self.getTask(task_id)
                if task["state"] in ("finished", "error", "canceled"):
                    results[task["task_id"]] = task
                    if self.is_task_successful(task):
                        log.debug("Task successful: %s, %s" % (task["task_id"],
                                  self.resolve_task_type(task)))
                    else:
                        log.debug("Finished: Failed: %s" % (task))
                    finished.append(t)
            for t in [t for t in finished if not self.is_task_successful(t)]:
                if t.get("exception", None):
                    exception = u''.join(t["exception"])
                else:
                    exception = None
                if t.get("traceback", None):
                    traceback = u''.join(t["traceback"])
                else:
                    traceback = None
                try:
                    reasons = t.reasons
                except AttributeError:
                    result = t.get("result", {}) if t.get("result", {}) else {}
                    reasons = result.get('reasons', [])
                log.error(u"Pulp task [%s] failed:\n"
                          "Details:\n%s\nTags:\n%s\nReasons:\n%s\nException:\n%s\nTraceback:\n%s" %
                          (t["task_id"],
                           pprint.pformat(result.get('details', '')),
                           '\n'.join([str(x) for x in t.get("tags", [])]),
                           '\n'.join([str(x) for x in reasons]),
                           exception, traceback))
                failed_tasks.append(t)
                failed = True
            running -= set([t["task_id"] for t in finished])

            if failed and running:
                log.warning("Canceling running tasks: %s" % ', '.join(running))
                for task_id in running:
                    self.deleteTask(task_id)
                running = set()
                raise errors.DockPulpError("Pulp tasks failed: %s" % failed_tasks)

            if running and len(running) != running_count:
                log.debug("Waiting on the following %d Pulp tasks: %s" % (
                    len(running), ",".join(sorted(running))))
                running_count = len(running)
        return results.values()


def split_content_url(url):
    i = url.find('/content')
    return url[:i], url[i:]


def setup_logger(log):
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)-9s %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    return log
