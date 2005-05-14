from paste.util import thirdparty
thirdparty.add_package('wsgiutils')
from wsgiutils import wsgiServer

def serve(conf, app):
    server = wsgiServer.WSGIServer(
        (conf.get('host', 'localhost'),
         int(conf.get('port', 8080))), {'': app})
    server.serve_forever()

description = """\
WSGIUtils is a small threaded server using Python's standard
SimpleHTTPServer.
"""

options = {
    'port': 'Port to serve on (default: 8080)',
    'host': 'Host to serve from (default: localhost, which is only accessible from the local computer; use 0.0.0.0 to make your application public)',
    }