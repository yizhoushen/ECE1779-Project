from app import webapp_memcache
webapp_memcache.run('0.0.0.0',5001, debug=True, use_reloader=False)

# if __name__ == '__main__':
#     webapp_memcache.run('0.0.0.0',debug=True, use_reloader=False)