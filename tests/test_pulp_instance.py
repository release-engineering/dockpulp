#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, RequestsHttpCaller, errors, log
import pytest
import hashlib
import json
import requests
import tarfile
import logging
from tempfile import NamedTemporaryFile
from textwrap import dedent
from contextlib import nested
from flexmock import flexmock
log.setLevel(logging.CRITICAL)


# fixtures
@pytest.fixture
def pulp(tmpdir):
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt')) as (fp, df):
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
            beta = foobar
            ga = foobar
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
        pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name)
    return pulp


@pytest.fixture
def core_pulp(tmpdir):
    # No optional fields in dockpulp.conf
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt')) as (fp, df):
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
        core_pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name)
    return core_pulp


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


# tests
class TestPulp(object):
    # Tests of methods from Pulp class.
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

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTaskRetries(self, pulp, tid, url):
        result = 'task_received'
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .twice()
            .and_raise(requests.ConnectionError)
            .and_return(result))
        assert pulp.getTask(tid) == result

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTaskRetriesFail(self, pulp, tid, url):
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .twice()
            .and_raise(requests.ConnectionError))
        with pytest.raises(requests.ConnectionError):
            pulp.getTask(tid)

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
                               'tag': 'testtag'}},
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
            .twice()
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
            .twice()
            .and_raise(requests.exceptions.ConnectionError))
        response = pulp.checkBlobs(repo, blobs)
        assert response['error']

    @pytest.mark.parametrize('dist_id', ['foo', 'bar'])
    def test_associate(self, pulp, dist_id):
        if dist_id == 'bar':
            flexmock(RequestsHttpCaller)
            (RequestsHttpCaller
                .should_receive('__call__')
                .never())
            with pytest.raises(errors.DockPulpConfigError):
                pulp.associate(dist_id, 'testrepo')
        else:
            flexmock(RequestsHttpCaller)
            (RequestsHttpCaller
                .should_receive('__call__')
                .once()
                .and_return(None))
            response = pulp.associate(dist_id, 'testrepo')
            assert response is None

    @pytest.mark.parametrize('repo_id, productline', [('redhat-foo-bar', 'foo'),
                                                      ('foo-bar', 'foo'),
                                                      ('foo', None),
                                                      ('foo-bar-test', 'foo-bar')])
    @pytest.mark.parametrize('repotype, importer_type_id', [('foo', 'bar'), (None, None)])
    @pytest.mark.parametrize('url', [None, 'http://test', '/content/foo/bar'])
    @pytest.mark.parametrize('registry_id', [None, 'foo/bar'])
    @pytest.mark.parametrize('distributors', [True, False])
    @pytest.mark.parametrize('library', [True, False])
    @pytest.mark.parametrize('distribution', ['beta', 'ga', None])
    def test_createRepo(self, pulp, repo_id, url, registry_id, distributors, productline,
                        library, distribution, repotype, importer_type_id):
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(None))
        response = pulp.createRepo(repo_id=repo_id, url=url, registry_id=registry_id,
                                   distributors=distributors, productline=productline,
                                   library=library, distribution=distribution, repotype=repotype,
                                   importer_type_id=importer_type_id)
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

    @pytest.mark.parametrize('dist', ['beta', 'foo'])
    def test_getDistributionSig(self, pulp, core_pulp, dist):
        if dist == 'foo':
            with pytest.raises(errors.DockPulpConfigError):
                pulp.getDistributionSig(dist)
        else:
            response = pulp.getDistributionSig(dist)
            assert response
            with pytest.raises(errors.DockPulpConfigError):
                core_pulp.getDistributionSig(dist)
