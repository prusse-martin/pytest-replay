# -*- coding: utf-8 -*-
import os
import sys
from glob import glob


def pytest_addoption(parser):
    group = parser.getgroup('replay')
    group.addoption(
        '--replay-script-dir',
        action='store',
        dest='replay_script_dir',
        default=None,
        help='Set directory where to write shell scripts to reproduce runs.'
    )
    default_type = 'bat' if sys.platform.startswith('win') else 'sh'
    group.addoption(
        '--replay-script-ext',
        action='store',
        dest='replay_script_ext',
        default=default_type,
        help='Set the type of script to use. Default "{}".'.format(default_type),
    )


class ReplayWriter(object):
    BASE_SCRIPT_NAME = '.pytest-replay'

    def __init__(self, config):
        self.dir = config.getoption('replay_script_dir')
        self.ext = config.getoption('replay_script_ext')
        self.template = TEMPLATES[self.ext]
        self.cleanup_scripts()
        self.written_nodeids = set()
        nprocs = config.getoption('numprocesses', 0)
        self.running_xdist = nprocs is not None and nprocs > 1
        self.xdist_worker_name = os.environ.get('PYTEST_XDIST_WORKER')

    def pytest_runtest_logstart(self, nodeid):
        if self.running_xdist and not self.xdist_worker_name:
            # only workers report running tests when running in xdist
            return
        self.append_test_to_script(nodeid)

    def cleanup_scripts(self):
        if os.path.isdir(self.dir):
            mask = os.path.join(self.dir, self.BASE_SCRIPT_NAME + '*.' + self.ext)
            for fn in glob(mask):
                os.remove(fn)
        else:
            os.makedirs(self.dir)

    def append_test_to_script(self, nodeid):
        suffix = '-' + self.xdist_worker_name if self.xdist_worker_name else ''
        fn = os.path.join(self.dir, self.BASE_SCRIPT_NAME + suffix + '.' + self.ext)
        if not os.path.isfile(fn):
            with open(fn, 'w') as f:
                f.write(self.template.preamble)

        if nodeid in self.written_nodeids:
            return
        with open(fn, 'a') as f:
            f.write(self.template.test.format(nodeid=nodeid))
            self.written_nodeids.add(nodeid)


class TemplateBat:
    preamble = 'REM generated by pytest-replay\npytest %*'
    test = ' ^\n  "{nodeid}"'


class TemplateSh:
    preamble = '# generated by pytest-replay\npytest $*'
    test = " \\\n  '{nodeid}'"


TEMPLATES = {
    'bat': TemplateBat,
    'sh': TemplateSh,
}


def pytest_configure(config):
    if config.getoption('replay_script_dir'):
        config.pluginmanager.register(ReplayWriter(config), 'replay-writer')


def pytest_report_header(config):
    if config.getoption('replay_script_dir'):
        return 'replay dir: {} ({})'.format(config.getoption('replay_script_dir'),
                                            config.getoption('replay_script_ext'))
