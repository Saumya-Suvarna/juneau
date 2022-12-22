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

import json
import logging
import os
import datetime
import time

import pandas as pd
from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join

from juneau.config import config
from juneau.db.table_db import connect2db_engine, connect2gdb
from juneau.jupyter import jupyter
from juneau.search.search import search_tables
from juneau.store.variable import Var_Info
from juneau.store.store_func import Storage
from juneau.search.query import Query
from juneau.store.store_auth import UserInfoStorage
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors as errors

class JuneauHandler(IPythonHandler):
    """
    The Juneau Handler that coordinates the notebook server app instance. Essentially,
    this class is in charge of communicating the frontend with the backend via PUT and POST.
    """

    def initialize(self):
        """
        Initializes all the metadata related to a table in a Jupyter Notebook.
        Note we use `initialize()` instead of `__init__()` as per Tornado's docs:
        https://www.tornadoweb.org/en/stable/web.html#request-handlers

        The metadata related to the table is:
            - var: the name of the variable that holds the table.
            - kernel_id: the id of the kernel that executed the table.
            - cell_id: the id of the cell that created the table.
            - code: the actual code associated to creating the table.
            - mode: TODO
            - nb_name: the name of the notebook.
            - done: TODO
            - data_trans: TODO
            - graph_db: the Neo4J graph instance.
            - psql_engine: Postgresql engine.
            - store_graph_db_class: TODO
            - store_prov_db_class: TODO
            - prev_node: TODO

        Notes:
            Depending on the type of request (PUT/POST), some of the above will
            be present or not. For instance, the notebook name will be present
            on PUT but not on POST. That is why we check if the key is present in the
            dictionary and otherwise assign it to `None`.

            This function is called on *every* request.

        """
        data = self.request.arguments
        self.var = data["var"][0].decode("utf-8")
        self.kernel_id = data["kid"][0].decode("utf-8")
        self.code = data["code"][0].decode("utf-8")
        self.cell_id = (
            int(data["cell_id"][0].decode("utf-8")) if "cell_id" in data else None
        )
        self.mode = int(data["mode"][0].decode("utf-8")) if "mode" in data else None
        self.nb_name = data["nb_name"][0].decode("utf-8") if "nb_name" in data else None

        self.done = set()
        self.data_trans = {}
        self.store_class = Storage()

    def find_variable(self):
        """
        Finds and tries to return the contents of a variable in the notebook.

        Returns:
            tuple - the status (`True` or `False`), and the variable if `True`.
        """
        # Make sure we have an engine connection in case we want to read.
        if self.kernel_id not in self.done:
            o2, err = jupyter.exec_connection_to_psql(self.kernel_id)
            self.done.add(self.kernel_id)
            logging.info(o2)
            logging.info(err)

        logging.info(f"Looking up variable {self.var}")
        output, error = jupyter.request_var(self.kernel_id, self.var)
        logging.info("Returned with variable value.")

        if error or not output:
            sta = False
            return sta, error
        else:
            try:
                var_obj = pd.read_json(output, orient="split")
                sta = True
            except Exception as e:
                logging.error(f"Found error {e}")
                var_obj = None
                sta = False

        return sta, var_obj

    def put(self):
        logging.info(f"Juneau indexing request: {self.var}")
        logging.info(f"Stored tables: {self.application.indexed}")

        new_var = Var_Info(self.var, self.cell_id, self.nb_name, self.code)

        if new_var.store_name in self.application.indexed:
            logging.info("Request to index is already registered.")
        elif new_var.var_name not in new_var.code_list[-1]:
            logging.info("Not a variable in the current cell.")
        else:
            logging.info(f"Starting to store {new_var.var_name}")
            success, output = self.find_variable()

            if success:
                logging.info(f"Getting value of {new_var.var_name}")
                logging.info(output.head())

                new_var.get_value(output)

                if new_var.nb not in self.application.nb_cell_id_node:
                    self.application.nb_cell_id_node[new_var.nb] = {}
                try:
                    new_var.get_prev_node(self.application.nb_cell_id_node)
                    self.prev_node = self.store_class.store_table(new_var, self.application.schema_mapping_class)
                    if new_var.cid not in self.application.nb_cell_id_node[new_var.nb]:
                        self.application.nb_cell_id_node[new_var.nb][new_var.cid] = self.prev_node
                except Exception as e:
                    logging.error(f"Unable to store in graph store due to error {e}")
            else:
                logging.error("Find variable failed!")

        self.data_trans = {"res": "", "state": str("true")}
        self.write(json.dumps(self.data_trans))

    def post(self):
        logging.info("Juneau handling search request")
        if self.mode == 0:  # return table
            self.data_trans = {
                "res": "",
                "state": self.var in self.application.search_test_class.real_tables,
            }
            self.write(json.dumps(self.data_trans))
        else:
            success, output = self.find_variable()
            if success:
                codes = "\\n".join(self.code.strip("\\n#\\n").split("\\n#\\n"))
                query = Query(self.application.search_test_class.eng, self.cell_id, codes, self.var, self.nb_name, output)
                data_json = search_tables(
                    self.application.search_test_class, self.application.schema_mapping_class, self.mode, query)
                self.data_trans = {"res": data_json, "state": data_json != ""}
                self.write(json.dumps(self.data_trans))
            else:
                logging.error(f"The table was not found: {output}")
                self.data_trans = {"error": output, "state": False}
                self.write(json.dumps(self.data_trans))


class AuthCallback(IPythonHandler):
    def initialize(self):
        self.cred_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "credentials.json"
        )
        self.scopes = ['openid', 'https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']
        self.full_url= self.request.full_url()
        self.data_trans = {}

    def get(self):
        logging.info(f"Reached the authentication callback function")
        auth_state = ""
        if not self.get_cookie("auth_session_id"):
            self.write("Session id does not exist in cookie. Could not authenticate.")
            return
        else:
            session_id  = self.get_cookie("auth_session_id")[0]
            session_vals = self.application.session_info.get(session_id,"")
            if session_vals == "":
                self.write("Session does not exist. Could not authenticate.")
                return
            auth_state = session_vals.get('auth_state',"")
            if auth_state == "":
                self.write("State does not exist. Could not authenticate.")
                return
            try:
                flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                    self.cred_path, scopes=self.scopes, state=auth_state)
                flow.redirect_uri = url_path_join("http://" + self.settings.get('ip', '127.0.0.1')+":"+self.settings.get('port', '8888'), self.settings.get('base_url', '/'), 'oauthcb')
                authorization_response = self.full_url
                flow.fetch_token(authorization_response=authorization_response)
                credentials = flow.credentials
                session_vals['credentials'] = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes,
                    'expiry': credentials.expiry
                    }
                self.application.session_info[session_id] = session_vals
            except Exception as err:
                self.write("Error while authentication: " + str(err))
                return
            user_info_service = googleapiclient.discovery.build(
                serviceName='oauth2', version='v2', credentials=credentials, cache_discovery=False)
            user_info = None
            try:
                user_info = user_info_service.userinfo().get().execute()
            except Exception as err:
                self.write("Error while getting user info: " + str(err))
                return
            usr = UserInfoStorage()
            try:
                usr.add_update_user(user_info["id"],user_info["email"],user_info["name"],
                    user_info["given_name"],credentials.token)
            except Exception as err:
                logging.error("Error while inserting user info into table: " + str(err))
                return
            self.set_cookie("auth_state", "Authenticated")
            self.write("Authenication complete")
            self.redirect(self.get_cookie("auth_redirect"))



class AuthHandler(IPythonHandler):
    def initialize(self):
        self.cred_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "credentials.json"
        )
        self.scopes = ['openid', 'https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']
        self.full_url= self.request.full_url()
        self.data_trans = {}
        
    # Refresh token: If the session information exists, refresh the token without
    def refresh_token(self, client_id, refresh_token, client_secret):
        params = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token
        }
        authorization_url = "https://oauth2.googleapis.com/token"
        try:
            r = requests.post(authorization_url, data=params)
            if r.ok:
                    return r.json()['access_token']
            else:
                return None
        except Exception as err:
            logging.info(f"Error occured while trying to refresh token: {err}")
            return None

    def post(self):
        logging.info(f"Starting Authorization")
        session_id = -1
        # if a session id exists for the current session, use it otherwise create a new session
        if not self.get_cookie("auth_session_id"):
            session_id = str(len(self.application.session_info) + 1)
            self.set_cookie("auth_session_id", str(session_id))
        else:
            session_id = self.get_cookie("auth_session_id")[0]

        if session_id not in self.application.session_info:
            self.application.session_info[session_id] = {}
        # if entry exists in session_info dict, check if needed to refresh token
        elif "credentials" in self.application.session_info[session_id]:
            creds = self.application.session_info[session_id]["credentials"]
            if "expiry" in creds and creds["expiry"] < datetime.datetime.now():
                try:
                    access_token = self.refresh_token(creds["client_id"], creds["refresh_token"], creds["client_secret"])
                    creds["token"] = access_token
                    self.application.session_info[session_id]["credentials"] = creds
                    self.set_cookie("auth_state", "Authenticated")
                    self.data_trans = {"error": "", "auth_state": "Authenticated", "auth_url": "", "auth_session_id": session_id}
                except Exception as err:
                    logging.error("Could not refresh token")
                    self.set_cookie("auth_state", "Failed")
                    self.data_trans = {"error": "Could not refresh token", "auth_state": "Failed", "auth_url": "", "auth_session_id": session_id}
                self.write(json.dumps(self.data_trans))
                return
            elif "expiry" in creds and creds["expiry"] > datetime.datetime.now():
                self.set_cookie("auth_state", "Authenticated")
                self.data_trans = {"error": "", "auth_state": "Authenticated", "auth_url": "", "auth_session_id": session_id}
                self.write(json.dumps(self.data_trans))
                return           
        try:
            # start the oauth flow
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(self.cred_path, scopes=self.scopes)
            flow.redirect_uri = url_path_join("http://"+ self.settings.get('ip', '127.0.0.1')+":"+self.settings.get('port', '8888'), self.settings.get('base_url', '/'), 'oauthcb')
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                prompt = 'select_account',
                include_granted_scopes='true')
            self.application.session_info[session_id]["auth_state"] = state
            self.data_trans = {"error": "", "auth_state": "In Progress", "auth_url": authorization_url, "auth_session_id": session_id}
            self.write(json.dumps(self.data_trans))
        except Exception as err:
            logging.error(f"Error occured while trying to authenticate", err)
            self.data_trans = {"error": str(err), "auth_state": "Failed", "auth_url": "", "auth_session_id":session_id}
            self.write(json.dumps(self.data_trans))

        