from flask import Flask

webapp_memcache = Flask(__name__)
memcache = {}

from app import main




