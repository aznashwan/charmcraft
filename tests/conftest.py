# Copyright 2020-2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For further info, check https://github.com/canonical/charmcraft

import datetime
import tempfile

import pytest
import responses as responses_module

from charmcraft import config as config_module


@pytest.fixture(autouse=True, scope="session")
def tmpdir_under_tmpdir(tmpdir_factory):
    tempfile.tempdir = str(tmpdir_factory.getbasetemp())


@pytest.fixture
def monkeypatch(monkeypatch):
    """Adapt pytest's monkeypatch to support stdlib's pathlib."""

    class Monkeypatcher:
        """Middle man for chdir."""

        def _chdir(self, value):
            """Change dir, but converting to str first.

            This is because Py35 monkeypatch doesn't support stdlib's pathlib.
            """
            return monkeypatch.chdir(str(value))

        def __getattribute__(self, name):
            if name == "chdir":
                return object.__getattribute__(self, "_chdir")
            else:
                return getattr(monkeypatch, name)

    return Monkeypatcher()


@pytest.fixture
def config(tmp_path):
    """Provide a config class with an extra set method for the test to change it."""

    class TestConfig(config_module.Config, frozen=False):
        """The Config, but with a method to set test values."""

        def set(self, prime=None, **kwargs):
            # prime is special, so we don't need to write all this structure in all tests
            if prime is not None:
                self.parts.__root__["bundle"] = config_module.Part(prime=prime)
            else:
                self.parts = config_module.Parts()

            # the rest is direct
            for k, v in kwargs.items():
                object.__setattr__(self, k, v)

    project = config_module.Project(
        dirpath=tmp_path, started_at=datetime.datetime.utcnow()
    )
    return TestConfig(type="bundle", project=project)


@pytest.fixture
def responses():
    """Simple helper to use responses module as a fixture, for easier integration in tests."""
    with responses_module.RequestsMock() as rsps:
        yield rsps
