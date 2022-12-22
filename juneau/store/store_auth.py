from juneau.config import config
import logging
from juneau.db.table_db import connect2db_engine
import psycopg2

class UserInfoStorage():

    def __init__(self):
        self.dbname = config.sql.dbname
        self.psql_eng = None

    def add_update_user(self,user_id, email, name, given_name, token):
        if not self.psql_eng:
            self.psql_eng = connect2db_engine(self.dbname)

        conn = self.psql_eng.connect()

        try:
            create_schema = f"create schema if not exists {config.sql.auth};"
            create_table = f"CREATE TABLE IF NOT EXISTS {config.sql.auth}.userinfo (user_id character varying(1000), email text unique, name character varying(1000), given_name character varying(1000), token character varying(1000),unique(email));"


            try:
                conn.execute(create_schema)
            except:
                logging.error("User Table: SCHEMA user_table ERROR!")

            try:
                conn.execute(create_table)
            except:
                logging.error("User Table: CREATE TABLE user_table ERROR!")

            table_insert = f"INSERT INTO {config.sql.auth}.userinfo (user_id, email, name, given_name, token) VALUES ('{user_id}', '{email}','{name}','{given_name}','{token}') ON CONFLICT (email) DO UPDATE SET user_id ='{user_id}', name = '{name}', given_name = '{given_name}' , token = '{token}'"
            try:
                conn.execute(table_insert)

            except:
                logging.error("User Table: INSERT UPDATE TABLE FAILED\n")

            return True

        except:
            logging.error("User Table: DATABASE CONNECTION ERROR!")
            return False