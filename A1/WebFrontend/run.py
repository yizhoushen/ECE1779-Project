#!../venv/bin/python

from app import webapp
webapp.run('0.0.0.0',5000,debug=True)

# from werkzeug.serving import run_simple
# from app import application

# if __name__ == '__main__':
#     run_simple('localhost', 5000, application, use_reloader=True, use_debugger=True, use_evalex=True)