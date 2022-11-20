from flask import Flask
import logging    # first of all import the module

logging.basicConfig(filename='std.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logging.warning('This message will get logged on to a file')

webapp_memcache = Flask(__name__)
memcache = {}

from app import main




