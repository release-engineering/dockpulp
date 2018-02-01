#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, Crane, RequestsHttpCaller, errors, log
import pytest
import hashlib
import json
import requests
import tarfile
import logging
import subprocess
from tempfile import NamedTemporaryFile
from textwrap import dedent
from contextlib import nested
from flexmock import flexmock
from requests.packages.urllib3.util import Retry
log.setLevel(logging.CRITICAL)


# fixtures
@pytest.fixture
def pulp(tmpdir):
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt'),
                NamedTemporaryFile(mode='wt')) as (fp, df, dn):
        name = 'test'
        fp.write(dedent("""
            [pulps]
            {name} = foo
            [registries]
            {name} = foo
            [filers]
            {name} = foo
            [redirect]
            {name} = no
            [distributors]
            {name} = foo
            [release_order]
            {name} = foo
            [retries]
            {name} = 2
            [signatures]
            foobar = foo
            [sig_exception]
            {name} = barfoo78
            """).format(name=name))
        fp.flush()

        df.write(dedent("""
            {
                "foo":{
                    "distributor_type_id": "docker_distributor_web",
                    "distributor_config": {}
                }
            }
            """))
        df.flush()

        dn.write(dedent("""
            {
                "beta":{
                    "signature": "foobar",
                    "name_enforce": "",
                    "content_enforce": "",
                    "name_restrict": ["-test"]
                },
                "test":{
                    "signature": "foobar",
                    "name_enforce": "-test",
                    "content_enforce": "/content/test",
                    "name_restrict": []
                }
            }
            """))
        dn.flush()
        pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name,
                    config_distributions=dn.name)
    return pulp


@pytest.fixture
def core_pulp(tmpdir):
    # No optional fields in dockpulp.conf
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt'),
                NamedTemporaryFile(mode='wt')) as (fp, df, dn):
        name = 'test'
        fp.write(dedent("""
            [pulps]
            {name} = foo
            [registries]
            {name} = foo
            [filers]
            {name} = foo
            [redirect]
            {name} = no
            [distributors]
            {name} = foo
            [release_order]
            {name} = foo
            """).format(name=name))
        fp.flush()

        df.write(dedent("""
            {
                "foo":{
                    "distributor_type_id": "docker_distributor_web",
                    "distributor_config": {}
                }
            }
            """))
        df.flush()

        dn.write(dedent("""
            {
                "foo":{
                    "signature": "",
                    "name_enforce": "",
                    "content_enforce": "",
                    "name_restrict": []
                }
            }
            """))
        dn.flush()
        core_pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name,
                         config_distributions=dn.name)
    return core_pulp


@pytest.fixture
def restricted_pulp(tmpdir):
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt'),
                NamedTemporaryFile(mode='wt')) as (fp, df, dn):
        name = 'test'
        fp.write(dedent("""
            [pulps]
            {name} = foo
            [registries]
            {name} = foo
            [filers]
            {name} = foo
            [redirect]
            {name} = no
            [distributors]
            {name} = foo
            [release_order]
            {name} = foo
            [retries]
            {name} = 2
            [signatures]
            foobar = foo
            [distribution]
            {name} = yes
            """).format(name=name))
        fp.flush()

        df.write(dedent("""
            {
                "foo":{
                    "distributor_type_id": "docker_distributor_web",
                    "distributor_config": {}
                }
            }
            """))
        df.flush()

        dn.write(dedent("""
            {
                "beta":{
                    "signature": "foobar",
                    "name_enforce": "",
                    "content_enforce": "",
                    "name_restrict": ["-test"]
                },
                "test":{
                    "signature": "foobar",
                    "name_enforce": "-test",
                    "content_enforce": "/content/test",
                    "name_restrict": []
                }
            }
            """))
        dn.flush()
        restricted_pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name,
                               config_distributions=dn.name)
    return restricted_pulp


@pytest.fixture
def crane(pulp):
    crane = Crane(pulp)
    return crane


# wrapper classes
class testRead(object):
    def read(self):
        return 'test'


class testResponse(object):
    def __init__(self):
        self.raw = testRead()


class testHash(object):
    def __init__(self, output):
        self.output = output

    def hexdigest(self):
        return self.output


HTTP_RETRIES_STATUS_FORCELIST = (500, 502, 503, 504)
fake_retry = Retry(total=1,
                   backoff_factor=1,
                   status_forcelist=HTTP_RETRIES_STATUS_FORCELIST)


# tests
class TestPulp(object):
    # Tests of methods from Pulp class.
    def test_switched_pulp(self):
        # Test for dockpulp switchover
        with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt'),
                    NamedTemporaryFile(mode='wt')) as (fp, df, dn):
            name = 'test'
            fp.write(dedent("""
                [pulps]
                {name} = foo
                [registries]
                {name} = foo
                [filers]
                {name} = foo
                [redirect]
                {name} = no
                [distributors]
                {name} = foo
                [release_order]
                {name} = foo
                [switch_ver]
                version = 10.0
                [switch_release]
                {name} = bar
            """).format(name=name))
            fp.flush()

            df.write(dedent("""
            {
                "foo":{
                    "distributor_type_id": "docker_distributor_web",
                    "distributor_config": {}
                },
                "switch":{
                    "distributor_type_id": "docker_distributor_web",
                    "distributor_config": {}
                }
            }
            """))
            df.flush()

            dn.write(dedent("""
            {
                "foo":{
                    "signature": "",
                    "name_enforce": "",
                    "content_enforce": "",
                    "name_restrict": []
                }
            }
            """))
            dn.flush()
            url = '/pulp/api/v2/status'
            response = {'versions': {'platform_version': '10.0'}}
            flexmock(RequestsHttpCaller)
            (RequestsHttpCaller
                .should_receive('__call__')
                .with_args('get', url)
                .and_return(response))
            switched_pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name,
                                 config_distributions=dn.name)
            assert switched_pulp.release_order == switched_pulp.switch_release
            response = {'versions': {'platform_version': '1.0'}}

            (RequestsHttpCaller
                .should_receive('__call__')
                .with_args('get', url)
                .and_return(response))
            switched_pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name,
                                 config_distributions=dn.name)
            assert switched_pulp.release_order != switched_pulp.switch_release

    @pytest.mark.parametrize('cert, key', [('foo', 'bar')])
    def test_set_certs(self, pulp, cert, key):
        pulp.set_certs(cert, key)
        assert pulp.certificate == cert
        assert pulp.key == key

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTask(self, pulp, tid, url):
        result = 'task_received'
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .once()
            .and_return(result))
        assert pulp.getTask(tid) == result

    def test_getPrefix(self, pulp):
        assert pulp.getPrefix() == 'redhat-'

    @pytest.mark.parametrize('rid, redirect', [
        ('test-repo', 'http://example/url'),
        ('test-repo', 'https://example/url'),
        ('test-repo', 'http://www.example.com/url/foo/bar'),
        ('test-repo', 'https://www.example.com/url/foo/bar')
    ])
    @pytest.mark.parametrize('dist', [None, 'beta'])
    def test_updateRedirect(self, pulp, rid, redirect, dist):
        update = {'redirect-url': redirect}
        blob = []
        did = {'distributor_type_id': 'testdist', 'id': 'test'}
        t = {'state': 'finished'}
        blob.append(did)
        if dist:
            update['notes'] = {'distribution': dist}
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, '111', t)
            .one_by_one())
        assert pulp.updateRepo(rid, update) is None

    @pytest.mark.parametrize('rid, redirect', [
        ('test-repo', 'test'),
        ('test-repo', 'example/test'),
        ('test-repo', 'https://example')
    ])
    def test_updateRedirectFail(self, pulp, rid, redirect):
        update = {'redirect-url': redirect}
        blob = []
        did = {'distributor_type_id': 'testdist', 'id': 'test'}
        t = {'state': 'finished'}
        blob.append(did)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, '111', t)
            .one_by_one())
        with pytest.raises(errors.DockPulpError):
            pulp.updateRepo(rid, update)

    @pytest.mark.parametrize('repos, content, history, label', [
        ('test-repo', True, True, True),
        ('test-repo', False, True, True),
    ])
    def test_listHistory(self, pulp, repos, content, history, label):
        blob = {'notes': {'_repo-type': 'docker-repo'}, 'id': 'testid', 'description': 'testdesc',
                'display_name': 'testdisp', 'distributors': [], 'scratchpad': {}}
        units = [{'unit_type_id': 'docker_manifest',
                  'metadata': {'fs_layers': [{'blob_sum': 'test'}], 'digest': 'testdig',
                               'tag': 'testtag', 'schema_version': 1}},
                 {'unit_type_id': 'docker_image', 'metadata': {'image_id': 'v1idtest'}}]
        labels = {'config': {'Labels': {'label1': 'label2'}}}
        v1Compatibility = {'parent': 'testparent', 'id': 'testid',
                           'config': {'Labels': {'testlab1': 'testlab2'}}}
        data = {'history': [{'v1Compatibility': json.dumps(v1Compatibility)}]}
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, units, labels, data)
            .one_by_one())
        history = pulp.listRepos(repos, content, history, label)
        for key in history[0]['manifests']:
            assert history[0]['manifests'][key]['v1parent'] == v1Compatibility['parent']
            assert history[0]['manifests'][key]['v1id'] == v1Compatibility['id']
            assert history[0]['manifests'][key]['v1labels']['testlab1'] == \
                v1Compatibility['config']['Labels']['testlab1']
        for key in history[0]['v1_labels']:
            assert history[0]['v1_labels'][key] == labels['config']['Labels']

    def test_listSigstore(self, pulp):
        repoid = pulp.getSigstore()
        blob = {'notes': {'_repo-type': 'iso'}, 'id': repoid,
                'description': 'testdesc', 'display_name': 'testdisp', 'distributors': [],
                'scratchpad': {}}
        units = [{'unit_type_id': 'iso', 'metadata': {'name': 'testname'}}]
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, units)
            .one_by_one())
        response = pulp.listRepos(repoid, content=True)
        assert response[0]['sigstore'][0] == 'testname'

    def test_listSchema2(self, pulp):
        blob = {'notes': {'_repo-type': 'docker-repo'}, 'id': 'testid', 'description': 'testdesc',
                'display_name': 'testdisp', 'distributors': [], 'scratchpad': {}}
        units = [{'unit_type_id': 'docker_manifest',
                  'metadata': {'fs_layers': [{'blob_sum': 'test_layer'}], 'digest': 'testdig',
                               'tag': 'testtag', 'config_layer': 'test_config',
                               'schema_version': 2}},
                 {'unit_type_id': 'docker_blob', 'metadata': {'digest': 'test_config'}},
                 {'unit_type_id': 'docker_blob', 'metadata': {'digest': 'test_layer'}}]
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, units)
            .one_by_one())
        response = pulp.listRepos('testid', content=True)
        assert response[0]['manifests']['testdig']['config'] == 'test_config'
        assert response[0]['manifests']['testdig']['layers'][0] == 'test_layer'
        assert response[0]['manifests']['testdig']['schema_version'] == 2

    @pytest.mark.parametrize('repo, image', [('testrepo', 'testimg')])
    def test_checkLayers(self, pulp, repo, image):
        images = []
        images.append(image)
        req = requests.Response()
        flexmock(
            req,
            raw="rawtest")
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(tarfile)
        (tarfile
            .should_receive('open')
            .once()
            .and_return(tarfile.TarFile))
        flexmock(tarfile.TarFile)
        (tarfile.TarFile
            .should_receive('close')
            .once()
            .and_return())
        response = pulp.checkLayers(repo, images)
        assert not response['error']

    @pytest.mark.parametrize('repo, image', [('testrepo', 'testimg')])
    def test_checkLayersFail(self, pulp, repo, image):
        images = []
        images.append(image)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_raise(requests.exceptions.ConnectionError))
        response = pulp.checkLayers(repo, images)
        assert response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'testblob')])
    def test_checkBlobs(self, pulp, repo, blob):
        blobs = []
        blobs.append('sha256:%s' % blob)
        req = testResponse()
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(hashlib)
        (hashlib
            .should_receive('sha256')
            .once()
            .and_return(testHash(blob)))
        response = pulp.checkBlobs(repo, blobs)
        assert not response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'testblob')])
    def test_checkBlobsMismatch(self, pulp, repo, blob):
        blobs = []
        blobs.append('sha256:%s' % blob)
        req = testResponse()
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(hashlib)
        (hashlib
            .should_receive('sha256')
            .once()
            .and_return(testHash('test')))
        response = pulp.checkBlobs(repo, blobs)
        assert response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'sha256:testblob')])
    def test_checkBlobsFail(self, pulp, repo, blob):
        blobs = []
        blobs.append(blob)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_raise(requests.exceptions.ConnectionError))
        response = pulp.checkBlobs(repo, blobs)
        assert response['error']

    @pytest.mark.parametrize('dist_id', ['foo', 'bar'])
    @pytest.mark.parametrize('type_id', [None, 'foobar'])
    def test_associate(self, pulp, dist_id, type_id):
        if dist_id == 'bar':
            flexmock(RequestsHttpCaller)
            (RequestsHttpCaller
                .should_receive('__call__')
                .never())
            with pytest.raises(errors.DockPulpConfigError):
                pulp.associate(dist_id, 'testrepo')
        else:
            url = '/pulp/api/v2/repositories/testrepo/distributors/'
            data = {
                "distributor_type_id": "docker_distributor_web",
                "distributor_config": {}
            }
            if type_id:
                data['distributor_type_id'] = type_id
            flexmock(RequestsHttpCaller)
            (RequestsHttpCaller
                .should_receive('__call__')
                .once()
                .with_args('post', url, data=json.dumps(data))
                .and_return(None))
            response = pulp.associate(dist_id, 'testrepo', type_id)
            assert response is None

    @pytest.mark.parametrize('repo_id, productline', [('redhat-foo-bar', 'foo'),
                                                      ('foo-bar', 'foo'),
                                                      ('foo', None),
                                                      ('bar', 'foo-test'),
                                                      ('tags-bar', 'bar'),
                                                      ('foo-blobs', 'blobs')])
    @pytest.mark.parametrize('repotype, importer_type_id, rel_url',
                             [('foo', 'bar', 'http://relurl'), (None, None, None)])
    @pytest.mark.parametrize('url', [None, 'http://test', '/content/test/foo-test/bar'])
    @pytest.mark.parametrize('registry_id', [None, 'foo/bar'])
    @pytest.mark.parametrize('distributors', [True, False])
    @pytest.mark.parametrize('library', [True, False])
    @pytest.mark.parametrize('distribution', ['beta', 'test', None])
    def test_createRepo(self, pulp, repo_id, url, registry_id, distributors, productline,
                        library, distribution, repotype, importer_type_id, rel_url):
        if distribution == 'test':
            if (url != '/content/test/foo-test/bar' and url is not None) or \
               ((productline is not None or library) and productline != 'foo-test'):
                with pytest.raises(errors.DockPulpError):
                    pulp.createRepo(repo_id=repo_id, url=url, registry_id=registry_id,
                                    distributors=distributors, productline=productline,
                                    library=library, distribution=distribution, repotype=repotype,
                                    importer_type_id=importer_type_id, rel_url=rel_url)
                return
        if distribution == 'beta' and productline and productline.endswith('test'):
            with pytest.raises(errors.DockPulpError):
                pulp.createRepo(repo_id=repo_id, url=url, registry_id=registry_id,
                                distributors=distributors, productline=productline,
                                library=library, distribution=distribution, repotype=repotype,
                                importer_type_id=importer_type_id, rel_url=rel_url)
            return
        if not registry_id and (repo_id == 'tags' or productline == 'blobs'):
            with pytest.raises(errors.DockPulpError):
                pulp.createRepo(repo_id=repo_id, url=url, registry_id=registry_id,
                                distributors=distributors, productline=productline,
                                library=library, distribution=distribution, repotype=repotype,
                                importer_type_id=importer_type_id, rel_url=rel_url)
            return
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(None))
        response = pulp.createRepo(repo_id=repo_id, url=url, registry_id=registry_id,
                                   distributors=distributors, productline=productline,
                                   library=library, distribution=distribution, repotype=repotype,
                                   importer_type_id=importer_type_id, rel_url=rel_url)
        if not repo_id.startswith(pulp.getPrefix()):
            repo_id = pulp.getPrefix() + repo_id
        if registry_id is None:
            if productline:
                pindex = repo_id.find(productline)
                registry_id = productline + '/' + repo_id[pindex + len(productline) + 1:]
            elif library:
                registry_id = repo_id.replace(pulp.getPrefix(), '')
            else:
                registry_id = repo_id.replace(pulp.getPrefix(), '').replace('-', '/', 1)
        rurl = url
        if rurl and not rurl.startswith('http'):
            rurl = pulp.cdnhost + url
        assert response['id'] == repo_id
        assert response['display_name'] == repo_id
        if distribution:
            assert response['notes']['distribution'] == distribution
            sig = pulp.getDistributionSig(distribution)
            assert response['notes']['signatures'] == pulp.getSignature(sig)
        if distributors:
            assert response['distributors'][0]['distributor_config']['repo-registry-id'] \
                == registry_id
            assert response['distributors'][0]['distributor_config']['redirect-url'] == rurl
        if repotype:
            assert response['notes']['_repo-type'] == repotype
        if importer_type_id:
            assert response['importer_type_id'] == importer_type_id
        if rel_url:
            assert response['notes']['relative_url'] == rel_url

    def test_disassociate(self, pulp):
        repo = 'testrepo'
        dist_id = 'foo'
        dl = '/pulp/api/v2/repositories/%s/distributors/%s/' % (repo, dist_id)
        tid = '123'
        url = '/pulp/api/v2/tasks/%s/' % tid
        t = {'state': 'finished'}
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('delete', dl)
            .once()
            .and_return(tid))
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .once()
            .and_return(t))
        response = pulp.disassociate('foo', 'testrepo')
        assert response is None

    @pytest.mark.parametrize('repo_id', ['redhat-everything', 'redhat-sigstore', 'redhat-foo-bar'])
    def test_create_hidden(self, restricted_pulp, repo_id):
        if repo_id == 'redhat-foo-bar':
            with pytest.raises(errors.DockPulpError):
                restricted_pulp.createRepo(repo_id=repo_id, url='/foo/bar', library=True)
            return
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(None))
        response = restricted_pulp.createRepo(repo_id=repo_id, url='/foo/bar', library=True)
        assert response['id'] == repo_id

    @pytest.mark.parametrize('publish', [True, False])
    def test_deleteRepo(self, pulp, publish):
        repo = 'foobar'
        flexmock(Pulp)
        if publish:
            (Pulp
                .should_receive('emptyRepo')
                .with_args(repo)
                .once()
                .and_return(None))
            (Pulp
                .should_receive('crane')
                .with_args(repo, force_refresh=True)
                .twice()
                .and_return(None))
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('delete', '/pulp/api/v2/repositories/%s/' % repo)
            .once()
            .and_return(123))
        (Pulp
            .should_receive('watch')
            .with_args(123)
            .once()
            .and_return(None))
        pulp.deleteRepo(repo, publish)

    def test_emptyRepo(self, pulp):
        repo = 'foobar'
        flexmock(Pulp)
        (Pulp
            .should_receive('remove_filters')
            .with_args(repo)
            .once()
            .and_return(None))
        pulp.emptyRepo(repo)

    def test_remove_filters(self, pulp):
        repo = 'foobar'
        type_ids = ['docker_image', 'docker_manifest', 'docker_blob', 'docker_tag',
                    'docker_manifest_list']
        data = {
            'criteria': {
                'type_ids': type_ids,
                'filters': {},
            },
            'override_config': {},
            'limit': 1
        }
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('post', '/pulp/api/v2/repositories/%s/actions/unassociate/' % repo,
                       data=json.dumps(data))
            .once()
            .and_return(123))
        flexmock(Pulp)
        (Pulp
            .should_receive('watch')
            .with_args(123)
            .once()
            .and_return(None))
        pulp.remove_filters(repo)

    def test_sync(self, pulp):
        repoinfoold = [{'id': 'redhat-foobar', 'images': {}, 'manifests': {'123456': 'foobar'}}]
        repoinfonew = [{'id': 'redhat-foobar', 'images': {}, 'manifests': {'123456': 'foobar',
                                                                           '567890': 'latest'}}]
        pulp_filter = {'unit': {'$or': [{'digest': '567890'}]}}
        flexmock(pulp)
        (pulp
            .should_receive('listRepos')
            .with_args(repos='redhat-foobar', content=True)
            .twice()
            .and_return(repoinfoold, repoinfonew)
            .one_by_one())
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return('123'))
        (pulp
            .should_receive('watch')
            .with_args('123')
            .once()
            .and_return(None))
        (pulp
            .should_receive('copy_filters')
            .with_args('redhat-everything', 'redhat-foobar', pulp_filter)
            .once()
            .and_return(None))
        imgs, manifests = pulp.syncRepo(env='syncenv', repo='foobar', feed='fb',
                                        upstream_name='foobar')
        assert imgs == []
        assert manifests == ['567890']


class TestCrane(object):
    # Tests of methods of Crane class.
    @pytest.mark.parametrize('error', [True, False])
    def test_confirm(self, crane, pulp, error):
        repos = 'test-repo'
        repoinfo = [{'id': 'test-repo', 'detail': 'foobar',
                     'images': {'testimage': ['testtag']},
                     'v1_labels': {'testimage': {'testkey': 'testval'}},
                     'manifests': {'testmanifest': {'layers': ['testlayer1'], 'tag': 'testtag',
                                                    'config': 'testconfig',
                                                    'schema_version': 'testsv',
                                                    'v1id': 'testv1id',
                                                    'v1parent': 'testv1parent',
                                                    'v1labels': 'testv1labels'}},
                     'manifest_lists': {'testmanifestlist': {'mdigests': ['testmanifest'],
                                                             'tags': ['testtag']}},
                     'tags': {'testtag': 'testmanifest'},
                     'docker-id': 'testdockerid',
                     'redirect': 'testredirect',
                     'protected': False}]
        imgs = ['testimage']
        manifests = ['testmanifest']
        manifest_lists = ['testmanifestlist']
        blobs = ['testlayer1']
        # duplicate tags allowed
        tags = ['testtag', 'testtag']
        repo = repoinfo[0]
        repoids = {repo['id']: {}}
        if error:
            repoids['numerrors'] = 4
        else:
            repoids['numerrors'] = 0
        repoids[repo['id']]['error'] = error
        response = {'error': error}
        flexmock(pulp)
        (pulp
            .should_receive('listRepos')
            .with_args(repos=repos, content=True)
            .once()
            .and_return(repoinfo))
        flexmock(crane)
        (crane
            .should_receive('_test_repo')
            .with_args(repo['docker-id'], repo['redirect'], imgs, repo['protected'], True)
            .once()
            .and_return(response))
        (crane
            .should_receive('_test_repoV2')
            .with_args(repo, repo['docker-id'], repo['id'], repo['redirect'], manifests,
                       manifest_lists, blobs, tags, repo['protected'], True)
            .once()
            .and_return(response))
        (pulp
            .should_receive('checkLayers')
            .with_args(repo['id'], imgs)
            .once()
            .and_return(response))
        (pulp
            .should_receive('checkBlobs')
            .with_args(repo['id'], blobs)
            .once()
            .and_return(response))
        assert crane.confirm(repos, check_layers=True) == repoids

    def test_confirm_sigstore(self, crane, pulp):
        repos = pulp.getSigstore()
        repoinfo = [{'id': repos, 'sigstore': 'image@shasum'}]
        response = {'error': False}
        flexmock(pulp)
        (pulp
            .should_receive('listRepos')
            .with_args(repos=repos, content=True)
            .once()
            .and_return(repoinfo))
        flexmock(crane)
        (crane
            .should_receive('_test_sigstore')
            .with_args(repoinfo[0]['sigstore'], exception='barfoo78')
            .once()
            .and_return(response))
        crane.confirm(repos)

    @pytest.mark.parametrize('signatures, status, ok, shasum, status2, ok2, expected_result', [
        (None, None, None, None, None, None, None),
        (['foo/bar-1@shasum=123/signature-1'], 200, True, '12345678\n', 200, True,
         {'error': False, 'sigs_in_pulp_not_crane': [],
          'sigs_in_crane_not_pulp': [], 'invalid_sigs': [],
          'manifests_in_sigstore_not_repo': [],
          'missing_repos_in_pulp': []}),
        (['foo/bar-2@shasum=234/signature-1'], 404, False, '12345678\n', 200, True,
         {'error': True, 'sigs_in_pulp_not_crane': ['foo/bar-2@shasum=234/signature-1'],
          'sigs_in_crane_not_pulp': ['foo/bar-1@shasum=123/signature-1'], 'invalid_sigs': [],
          'manifests_in_sigstore_not_repo': [],
          'missing_repos_in_pulp': []}),
        (['foo/bar-3@shasum=345/signature-1'], 200, True, '12345678\n', 404, False,
         {'error': True, 'sigs_in_pulp_not_crane': [],
          'sigs_in_crane_not_pulp': [], 'invalid_sigs': [],
          'manifests_in_sigstore_not_repo': [],
          'missing_repos_in_pulp': []}),
        (['foo/bar-4@shasum=456/signature-1'], 200, True, '87654321\n', 200, True,
         {'error': True, 'sigs_in_pulp_not_crane': [],
          'sigs_in_crane_not_pulp': ['foo/bar-1@shasum=123/signature-1'],
          'invalid_sigs': ['foo/bar-4@shasum=456/signature-1'],
          'manifests_in_sigstore_not_repo': [],
          'missing_repos_in_pulp': []})])
    def test_test_sigstore(self, crane, pulp, signatures, status, ok, shasum, status2, ok2,
                           expected_result):
        if signatures is None:
            response = crane._test_sigstore(signatures)
            assert response == {'error': False, 'sigs_in_pulp_not_crane': [],
                                'sigs_in_crane_not_pulp': [], 'invalid_sigs': [],
                                'manifests_in_sigstore_not_repo': [],
                                'missing_repos_in_pulp': []}
            return
        (repo, manifest) = crane._split_signature(signatures[0], 'redhat-')
        prefix = pulp.getPrefix()
        if not repo.startswith(prefix):
            repo = prefix + repo
        pulp_repos = [{'id': repo, 'signatures': '12345678', 'manifests': {manifest: 'foobar'}}]
        flexmock(pulp)
        (pulp
            .should_receive('listRepos')
            .once()
            .and_return(pulp_repos))
        url = 'foo/content/sigstore/'
        signature = signatures[0]
        answer = flexmock(
            status_code=status,
            ok=ok,
            content="junkdata")
        flexmock(requests.Session)
        (requests.Session
            .should_receive('get')
            .with_args(url + signature, verify=False)
            .once()
            .and_return(answer))
        flexmock(subprocess.Popen)
        (subprocess.Popen
            .should_receive('communicate')
            .once()
            .and_return(['', shasum]))
        answer2 = flexmock(
            status_code=status2,
            ok=ok2,
            text='foo/bar-1@shasum=123/signature-1')
        (requests.Session
            .should_receive('get')
            .with_args(url + 'PULP_MANIFEST', verify=False)
            .once()
            .and_return(answer2))
        response = crane._test_sigstore(signatures)
        assert response == expected_result

    @pytest.mark.parametrize('sslerror', [True, False])
    @pytest.mark.parametrize('pulp_manifests', [[], ['testmanifest']])
    def test_test_repoV2(self, crane, pulp, sslerror, pulp_manifests):
        repo = {'id': 'test-repo', 'detail': 'foobar',
                'images': {'testimage': ['testtag']},
                'v1_labels': {'testimage': {'testkey': 'testval'}},
                'manifests': {'testmanifest': {'layers': ['testlayer1'],
                                               'tag': 'testtag',
                                               'config': {'digest': 'testlayer1'},
                                               'schema_version': '2',
                                               'v1id': 'testv1id',
                                               'v1parent': 'testv1parent',
                                               'v1labels': 'testv1labels'}},
                'manifest_lists': {'testmanifestlist': {'mdigests': ['testmanifest'],
                                                        'tags': ['testtag']}},
                'tags': {'testtag': 'testmanifest'},
                'docker-id': 'testdockerid',
                'redirect': 'testredirect',
                'protected': False}
        dockerid = 'testdockerid'
        repoid = 'test-repo'
        redirect = 'testredirect'
        pulp_manifests = ['testmanifest']
        pulp_manifest_lists = ['testmanifestlist']
        # both config blob and digest blob have to be the same
        # otherwise result will never match due to list(set()) in test_repoV2
        pulp_blobs = ['testlayer1']
        pulp_tags = ['testtag', 'testtag']
        protected = False
        silent = True
        result = {'error': False}

        if not pulp_manifests:
            response = crane._test_repoV2(repo, dockerid, repoid, redirect, pulp_manifests,
                                          pulp_manifest_lists, pulp_blobs, pulp_tags, protected,
                                          silent)
            assert response == result
            return
        result['crane_manifests_incorrectly_named'] = []
        result['incorrect_mediatype'] = []
        url = pulp.registry + '/v2/' + dockerid + '/manifests'

        flexmock(requests.Session)
        if sslerror:
            (requests.Session
                .should_receive('get')
                .with_args(url + '/' + 'testmanifest', verify=False, cert=(crane.cert, crane.key))
                .once()
                .and_raise(requests.exceptions.SSLError))
            result['error'] = True
            response = crane._test_repoV2(repo, dockerid, repoid, redirect, pulp_manifests,
                                          pulp_manifest_lists, pulp_blobs, pulp_tags, protected,
                                          silent)
            assert response == result
            return

        mediatype = 'application/vnd.docker.distribution.manifest.v2+json'
        fake_answer = flexmock(json=lambda: {'mediaType': mediatype,
                                             'layers': [{'digest': 'testlayer1'}],
                                             'config': {'digest': 'testlayer1'}},
                               content="testcontent",
                               status_code="teststatus",
                               ok=True)
        (requests.Session
            .should_receive('get')
            .with_args(url + '/' + 'testmanifest', verify=False, cert=(crane.cert, crane.key))
            .once()
            .and_return(fake_answer))
        result['manifests_in_pulp_not_crane'] = []
        result['reachable_manifests'] = pulp_manifests

        mediatype = 'application/vnd.docker.distribution.manifest.list.v2+json'
        fake_answer = flexmock(json=lambda: {'mediaType': mediatype},
                               content="testcontent",
                               status_code="teststatus",
                               ok=True)
        (requests.Session
            .should_receive('get')
            .with_args(url + '/' + 'testmanifestlist', verify=False, cert=(crane.cert, crane.key))
            .once()
            .and_return(fake_answer))
        result['manifest_lists_in_pulp_not_crane'] = []
        result['reachable_manifest_lists'] = pulp_manifest_lists

        url = pulp.registry + '/v2/' + dockerid + '/blobs/'
        flexmock(requests)
        (requests
            .should_receive('head')
            .with_args(url + 'testlayer1', verify=False, cert=(crane.cert, crane.key),
                       allow_redirects=True)
            .once()
            .and_return(fake_answer))
        result['blobs_in_pulp_not_crane'] = []
        result['reachable_blobs'] = ['testlayer1']

        url = pulp.registry + '/v2/' + dockerid + '/tags/list'
        fake_answer = flexmock(json=lambda: {'mediatype': mediatype},
                               content='{"name": "%s", "tags": ["testtag", "testtag"]}' % dockerid,
                               status_code="teststatus",
                               ok=True)
        (requests
            .should_receive('get')
            .with_args(url, verify=False, cert=(crane.cert, crane.key))
            .once()
            .and_return(fake_answer))
        result['tags_in_pulp_not_crane'] = []
        result['tags_in_crane_not_pulp'] = []
        result['reachable_tags'] = ['testtag']

        response = crane._test_repoV2(repo, dockerid, repoid, redirect, pulp_manifests,
                                      pulp_manifest_lists, pulp_blobs, pulp_tags, protected,
                                      silent)
        assert response == result


class TestRequestsHttpCaller(object):
    # Tests of methods from RequestsHttpCaller class.
    @pytest.mark.parametrize('status_code', HTTP_RETRIES_STATUS_FORCELIST)
    def test_getTaskRetriesFail(self, pulp, status_code):
        rq = RequestsHttpCaller('http://httpbin.org/')
        flexmock(Retry).new_instances = fake_retry
        with pytest.raises(requests.exceptions.RetryError):
            rq('get', '/status/%s' % status_code)
