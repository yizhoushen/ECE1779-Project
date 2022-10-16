from flask import Flask
from MemCache import webapp_mamcache

webapp_memcache = Flask(__name__)
memcache = {}

from MemCache import main




