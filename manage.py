# -*- coding: utf-8 -*-
from flask_script import Manager, Server
from api_end_points_v11 import app

manager = Manager(app)
manager.add_command("runserver", Server(host="0.0.0.0", port=8070, use_debugger=True, use_reloader=True, threaded=True))


if __name__ == '__main__':
    manager.run()
