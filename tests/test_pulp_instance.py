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
    def test_set_certs(self, pulp):
        pulp.set_certs('foo', 'bar')
        assert pulp.certificate == 'foo'
        assert pulp.key == 'bar'

    def test_getTask(self, pulp):
        flexmock(RequestsHttpCaller)
        RequestsHttpCaller.should_receive('__call__').with_args('get', '/pulp/api/v2/tasks/111/').once().and_return('well_done')
        assert pulp.getTask("111") == 'well_done'

    def test_getPrefix(self, pulp):
        assert pulp.getPrefix() == 'redhat-'
