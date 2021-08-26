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

"""A client to hit the Store."""

import logging
import os
import pathlib
import platform
import webbrowser
from json.decoder import JSONDecodeError
from typing import Any, Dict

import appdirs
import craft_store
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from charmcraft import __version__, utils
from charmcraft.cmdbase import CommandError


logger = logging.getLogger("charmcraft.commands.store")

TESTING_ENV_PREFIXES = ["TRAVIS", "AUTOPKGTEST_TMP"]


def build_user_agent():
    """Build the charmcraft's user agent."""
    if any(key.startswith(prefix) for prefix in TESTING_ENV_PREFIXES for key in os.environ.keys()):
        testing = " (testing) "
    else:
        testing = " "
    os_platform = "{0.system}/{0.release} ({0.machine})".format(utils.get_os_platform())
    return "charmcraft/{}{}{} python/{}".format(
        __version__, testing, os_platform, platform.python_version()
    )


def visit_page_with_browser(visit_url):
    """Open a browser so the user can validate its identity."""
    logger.warning(
        "Opening an authorization web page in your browser; if it does not open, "
        "please open this URL: %s",
        visit_url,
    )
    webbrowser.open(visit_url, new=1)


def _storage_push(monitor, storage_base_url) -> Dict[str, Any]:
    """Push bytes to the storage."""
    url = storage_base_url + "/unscanned-upload/"
    headers = {
        "Content-Type": monitor.content_type,
        "Accept": "application/json",
    }
    client = craft_store.HTTPClient(user_agent=build_user_agent())

    return client.post(url, headers=headers, data=monitor).json()


class Client(craft_store.StoreClient):
    """Lightweight layer above _AuthHolder to present a more network oriented interface."""

    def __init__(self, api_base_url, storage_base_url):
        config_path = pathlib.Path(appdirs.user_config_dir("charmcraft.creds"))
        api_base_url = api_base_url.rstrip("/")
        self.storage_base_url = storage_base_url.rstrip("/")

        super().__init__(
            base_url=api_base_url,
            config_path=config_path,
            endpoints=craft_store.endpoints.CHARMHUB,
            user_agent=build_user_agent(),
        )

    def request(self, method, url, *args, **kwargs) -> requests.Response:
        try:
            return super().request(method, url, *args, **kwargs)
        except craft_store.errors.StoreClientError as store_error:
            raise CommandError(str(store_error)) from store_error

    def request_json(self, *args, **kwargs) -> Dict[str, Any]:
        """Return .json() from a request.Response."""
        response = self.request(*args, **kwargs)
        try:
            return response.json()
        except JSONDecodeError as json_error:
            raise CommandError(
                f"Could not retrieve json response ({response.status_code} from request"
            ) from json_error

    def push_file(self, filepath):
        """Push the bytes from filepath to the Storage."""
        logger.debug("Starting to push %r", str(filepath))


        def _progress(monitor):
            # XXX Facundo 2020-07-01: use a real progress bar
            if monitor.bytes_read <= monitor.len:
                progress = 100 * monitor.bytes_read / monitor.len
                print("Uploading... {:.2f}%\r".format(progress), end="", flush=True)

        with filepath.open("rb") as fh:
            encoder = MultipartEncoder(
                fields={"binary": (filepath.name, fh, "application/octet-stream")}
            )

            # create a monitor (so that progress can be displayed) as call the real pusher
            monitor = MultipartEncoderMonitor(encoder, _progress)
            response = _storage_push(monitor, self.storage_base_url)

        result = response
        if not result["successful"]:
            raise CommandError("Server error while pushing file: {}".format(result))

        upload_id = result["upload_id"]
        logger.debug("Uploading bytes ended, id %s", upload_id)
        return upload_id
