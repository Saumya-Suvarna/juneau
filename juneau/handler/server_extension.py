# Copyright 2020 Juneau
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Main entry point for the server extension.
"""
import os
from notebook.utils import url_path_join
from juneau.config import config
from juneau.handler.handler import JuneauHandler, AuthHandler, AuthCallback
from juneau.search.search_cases import WithProv_Cached
from juneau.schemamapping.schemamapping import SchemaMapping


def load_jupyter_server_extension(nb_server_app):
    """
    Registers the `JuneauHandler` with the notebook server.

    Args:
        nb_server_app (NotebookWebApplication): handle to the Notebook webserver instance.
    """
    nb_server_app.log.info("Juneau extension loading...")

    # Inject global application variables.
    web_app = nb_server_app.web_app
    web_app.indexed = set()
    web_app.nb_cell_id_node = {}
    web_app.search_test_class = WithProv_Cached(config.sql.dbs)
    web_app.schema_mapping_class = SchemaMapping()
    web_app.session_info = {}
    route_pattern = url_path_join(web_app.settings["base_url"], "/juneau")
    auth_pattern = url_path_join(web_app.settings["base_url"], "/oauth")
    auth_cb_pattern = url_path_join(web_app.settings["base_url"], "/oauthcb")
    web_app.add_handlers(".*$", [(route_pattern, JuneauHandler), (auth_pattern, AuthHandler), (auth_cb_pattern, AuthCallback)])
    nb_server_app.log.info("Juneau extension loaded.")
