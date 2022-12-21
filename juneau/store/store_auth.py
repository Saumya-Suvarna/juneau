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
            query1 = f"create schema if not exists {config.sql.auth};"
            query2 = f"CREATE TABLE IF NOT EXISTS {config.sql.auth}.userinfo (user_id character varying(1000), email character varying(1000) UNIQUE, \
+        name character varying(1000), given_name character varying(1000), token character varying(1000));"


            try:
                conn.execute(query1)
            except:
                logging.error("User Table: SCHEMA user_table ERROR!")

            try:
                conn.execute(query2)
            except:
                logging.error("User Table: CREATE TABLE user_table ERROR!")

            query3 = f"""INSERT INTO {config.sql.auth}.userinfo (user_id, email, name, given_name, token)
                        VALUES ('{user_id}', '{email}','{name}','{given_name}','{token}')
                        ON CONFLICT ( '{email}')
                        DO UPDATE SET user_id ='{user_id}'
                                   , email = '{email}'
                                   , given_name = '{given_name}'
                                   , token = '{token}'
                    """

            try:
                conn.execute(query3)

            except:
                logging.error("User Table: INSERT UPDATE TABLE FAILED\n")

            return True

        except:
            logging.error("User Table: DATABASE CONNECTION ERROR!")
            return False