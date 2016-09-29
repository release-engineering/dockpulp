#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, RequestsHttpCaller
import pytest
from tempfile import NamedTemporaryFile
from textwrap import dedent
from contextlib import nested
from flexmock import flexmock


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
            """).format(name=name))
        fp.flush()

        df.write(dedent("""
            {}
            """))
        df.flush()
        pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name)
    return pulp


# tests
class TestPulp(object):
    # Tests of methods from Pulp class.
    @pytest.mark.parametrize('cert, key', [('foo', 'bar')])
    def test_set_certs(self, pulp, cert, key):
        pulp.set_certs(cert, key)
        assert pulp.certificate == cert
        assert pulp.key == key

    @pytest.mark.parametrize('tid, url, result', [
        ('111', '/pulp/api/v2/tasks/111/', 'task_received')
    ])
    def test_getTask(self, pulp, tid, url, result):
        flexmock(RequestsHttpCaller)
        RequestsHttpCaller.should_receive('__call__').with_args('get', url).once().and_return(result)
        assert pulp.getTask(tid) == result

    def test_getPrefix(self, pulp):
        assert pulp.getPrefix() == 'redhat-'
