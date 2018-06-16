import os
import xmlrpc.client
from configparser import ConfigParser
import logging
from logging.config import dictConfig


class API(object):
    dictConfig({
        'version': 1,
        'formatters': {
            'f': {'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'}
        },
        'handlers': {
            'h': {'class': 'logging.StreamHandler', 'formatter': 'f', 'level': logging.DEBUG}
        },
        'root': {
            'handlers': ['h'],
            'level': logging.INFO,
        }
    })
    logger = logging.getLogger()
    _config_parser = ConfigParser()
    _config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'settings.ini'))

    _config_parser.read(_config_file)

    _url = _config_parser.get("server", "host")
    _port = _config_parser.get("server", "port")
    _database = _config_parser.get("server", "database")
    _username = _config_parser.get("user", "username")
    _password = _config_parser.get("user", "password")

    common = xmlrpc.client.ServerProxy('http://{}:{}/xmlrpc/2/common'.format(
        _url, _port
    ))
    orm = xmlrpc.client.ServerProxy('http://{}:{}/xmlrpc/2/object'.format(
        _url, _port
    ))
    uid = common.authenticate(
        _database,
        _username,
        _password,
        {}
    )

    def init(self, url=False, port=False, database=False, username=False, password=False):
        self._url = url or self.config_parser.get("server", "host")
        self._port = port or self.config_parser.get("server", "port")
        self._database = database or self.config_parser.get("server", "database")
        self._username = username or self.config_parser.get("user", "username")
        self._password = password or self.config_parser.get("user", "password")

        self.common = xmlrpc.client.ServerProxy('http://{}:{}/xmlrpc/2/common'.format(
            self._url, self._port
        ))
        self.orm = xmlrpc.client.ServerProxy('http://{}:{}/xmlrpc/2/object'.format(
            self._url, self._port
        ))
        self.uid = self.common.authenticate(
            self._database,
            self._username,
            self._password,
            {}
        )
        self.uid = self.common.login(
            # _config_parser.get("server", "database"),
            # _config_parser.get("user", "username"),
            # _config_parser.get("user", "password")
            database,
            username,
            password
        )
        return self

    def do(self, model=None, action=None, params=None, context={}):
        res = self.orm.execute_kw(
            self._config_parser.get('server', 'database'),
            self.uid,
            self._config_parser.get('user', 'password'),
            model, action, params, context
        )

        return res

    def do(self, model=None, action=None, params=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._config_parser.get("server", "database"),
            self.uid,
            self._config_parser.get("user", "password"),
            model, action, params, context
        )

        return res

    def do_kw(self, model=None, action=None, params=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute_kw(
            self._config_parser.get("server", "database"),
            self.uid,
            self._config_parser.get("user", "password"),
            model, action, params, context
        )

        return res

    def do_2(self, model=None, action=None, params=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._config_parser.get("server", "database"),
            self.uid,
            self._config_parser.get("user", "password"),
            model, action, context
        )

        return res

    def do_new(self, model=None, action=None, ids=None, params=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._config_parser.get("server", "database"),
            self.uid,
            self._config_parser.get("user", "password"),
            model, action, ids, params, context
        )

        return res

    def commit_to_ofs(self, model=None, action=None, container_ref=None, verified_by=None, receipt_refs=None,
                      context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._database,
            self.uid,
            self._password,
            model, action, [], container_ref, verified_by, receipt_refs, context
        )

        return res

    def ofs_receive_dispatch(self, model=None, action=None, container_refs=None, delivery_date=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._database,
            self.uid,
            self._password,
            model, action, [], container_refs, delivery_date, context
        )

        return res

    def ofs_return_box(self, model=None, action=None, container_refs=None, context=None):
        if context is None:
            context = {}

        res = self.orm.execute(
            self._database,
            self.uid,
            self._password,
            model, action, [], container_refs, context
        )

        return res
