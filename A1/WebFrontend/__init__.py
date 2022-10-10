from flask import Flask

global memcache

webapp = Flask(__name__)
memcache = {}

from WebFrontend import main




