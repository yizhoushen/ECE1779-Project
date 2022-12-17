from flask import Flask

global memcache
global userid

webapp = Flask(__name__)
memcache = {}
userid = None

from app import main
from app import api
from app import account_op
from app import upload
from app import display
from app import config_memcache



