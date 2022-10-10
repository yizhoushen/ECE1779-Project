from werkzeug.middleware.dispatcher import DispatcherMiddleware

from WebFrontend import webapp as webfrontend
from MemCache import webapp as memcache

application = DispatcherMiddleware(webfrontend, {
    '/memcache': memcache
})