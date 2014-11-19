# Copyright 2014 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import functools
import logging as base_logging
import os
import shutil
import tempfile

from oslo.config import cfg

from cloudbaseinit.openstack.common import log as logging


CONF = cfg.CONF

__all__ = (
    'create_tempfile',
    'create_tempdir',
    'LogSnatcher',
    'ConfPatcher',
)


@contextlib.contextmanager
def create_tempdir():
    """Create a temporary directory.

    This is a context manager, which creates a new temporary
    directory and removes it when exiting from the context manager
    block.
    """
    tempdir = tempfile.mkdtemp(prefix="cloudbaseinit-tests")
    try:
        yield tempdir
    finally:
        shutil.rmtree(tempdir)


@contextlib.contextmanager
def create_tempfile(content=None):
    """Create a temporary file.

    This is a context manager, which uses `create_tempdir` to obtain a
    temporary directory, where the file will be placed.

    :param content:
        Additionally, a string which will be written
        in the new file.
    """
    with create_tempdir() as temp:
        fd, path = tempfile.mkstemp(dir=temp)
        os.close(fd)
        if content:
            with open(path, 'w') as stream:
                stream.write(content)
        yield path


# This is similar with unittest.TestCase.assertLogs from Python 3.4.
class SnatchHandler(base_logging.Handler):
    def __init__(self, *args, **kwargs):
        super(SnatchHandler, self).__init__(*args, **kwargs)
        self.output = []

    def emit(self, record):
        msg = self.format(record)
        self.output.append(msg)


class LogSnatcher(object):
    """A context manager to capture emitted logged messages.

    The class can be used as following::

        with LogSnatcher('plugins.windows.createuser') as snatcher:
            LOG.info("doing stuff")
            LOG.info("doing stuff %s", 1)
            LOG.warn("doing other stuff")
            ...
        self.assertEqual(snatcher.output,
                         ['INFO:unknown:doing stuff',
                          'INFO:unknown:doing stuff 1',
                          'WARN:unknown:doing other stuff'])
    """

    @property
    def output(self):
        return self._snatch_handler.output

    def __init__(self, logger_name):
        self._logger_name = logger_name
        self._snatch_handler = SnatchHandler()
        self._logger = logging.getLogger(self._logger_name)
        self._previous_level = self._logger.logger.getEffectiveLevel()

    def __enter__(self):
        self._logger.logger.setLevel(base_logging.DEBUG)
        self._logger.handlers.append(self._snatch_handler)
        return self

    def __exit__(self, *args):
        self._logger.handlers.remove(self._snatch_handler)
        self._logger.logger.setLevel(self._previous_level)


class ConfPatcher(object):
    """Override the configuration for the given key, with the given value.

    This class can be used both as a context manager and as a decorator.
    """
    # TODO(cpopa): mock.patch.dict would have been a better solution
    #              but oslo.config.cfg doesn't support item
    #              assignment.

    def __init__(self, key, value, conf=CONF):
        self._original_value = conf.get(key)
        self._key = key
        self._value = value
        self._conf = conf

    def __call__(self, func, *args, **kwargs):
        def _wrapped_f(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        functools.update_wrapper(_wrapped_f, func)
        return _wrapped_f

    def __enter__(self):
        self._conf.set_override(self._key, self._value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conf.set_override(self._key, self._original_value)
