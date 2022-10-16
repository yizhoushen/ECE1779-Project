from flask import Flask

webapp_memcache = Flask(__name__)
memcache = {}

from A1.MemCache import main




