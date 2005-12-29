# (c) 2005 Ian Bicking, Clark C. Evans and contributors
# This module is part of the Python Paste Project and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php
from paste.fileapp import *
from paste.fixture import *
from rfc822 import parsedate_tz, mktime_tz
import time, string

def test_data():
    harness = TestApp(DataApp('mycontent'))
    res = harness.get("/")
    assert 'application/octet-stream' == res.header('content-type')
    assert '9' == res.header('content-length')
    assert "<Response 200 OK 'mycontent'>" == repr(res)
    harness.app.set_content("bingles")
    assert "<Response 200 OK 'bingles'>" == repr(harness.get("/"))

def test_cache():
    def build(*args,**kwargs):
        app = DataApp("SomeContent")
        app.cache_control(*args,**kwargs)
        return TestApp(app).get("/")
    res = build()
    assert 'public' == res.header('cache-control')
    assert not res.header('expires',None)
    res = build(private=True)
    assert 'private' == res.header('cache-control')
    assert mktime_tz(parsedate_tz(res.header('expires'))) < time.time()
    res = build(no_cache=True)
    assert 'no-cache' == res.header('cache-control')
    assert mktime_tz(parsedate_tz(res.header('expires'))) < time.time()
    res = build(max_age=60,s_maxage=30)
    assert 'public, max-age=60, s-maxage=30' == res.header('cache-control')
    expires = mktime_tz(parsedate_tz(res.header('expires')))
    assert expires > time.time()+58 and expires < time.time()+61
    res = build(private=True, max_age=60, no_transform=True, no_store=True)
    assert 'private, no-store, no-transform, max-age=60' == \
           res.header('cache-control')
    expires = mktime_tz(parsedate_tz(res.header('expires')))
    assert mktime_tz(parsedate_tz(res.header('expires'))) < time.time()

def test_disposition():
    def build(*args,**kwargs):
        app = DataApp("SomeContent")
        app.content_disposition(*args,**kwargs)
        return TestApp(app).get("/")
    res = build()
    assert 'attachment' == res.header('content-disposition')
    assert 'application/octet-stream' == res.header('content-type')
    res = build(filename="bing.txt")
    assert 'attachment; filename="bing.txt"' == \
            res.header('content-disposition')
    assert 'text/plain' == res.header('content-type')
    res = build(inline=True)
    assert 'inline' == res.header('content-disposition')
    assert 'application/octet-stream' == res.header('content-type')
    res = build(inline=True, filename="/some/path/bing.txt")
    assert 'inline; filename="bing.txt"' == \
            res.header('content-disposition')
    assert 'text/plain' == res.header('content-type')
    try:
       res = build(inline=True,attachment=True)
    except AssertionError:
        pass
    else:
        assert False, "should be an exception"

def test_modified():
    harness = TestApp(DataApp('mycontent'))
    res = harness.get("/")
    assert "<Response 200 OK 'mycontent'>" == repr(res)
    res = harness.get("/",headers={'if-modified-since':
                                    res.header('last-modified')})
    assert "<Response 304 Not Modified ''>" == repr(res)
    res = harness.get("/",status=400,
            headers={'if-modified-since': 'garbage'})
    assert 400 == res.status and "ill-formed timestamp" in res.body
    res = harness.get("/",status=400,
            headers={'if-modified-since':
                'Thu, 22 Dec 2030 01:01:01 GMT'})
    assert 400 == res.status and "check your system clock" in res.body

def test_file():
    import random, string, os
    tempfile = "test_fileapp.%s.txt" % (random.random())
    content = string.letters * 20
    file = open(tempfile,"w")
    file.write(content)
    file.close()
    try:
        from paste import fileapp
        app = fileapp.FileApp(tempfile)
        res = TestApp(app).get("/")
        assert len(content) == int(res.header('content-length'))
        assert 'text/plain' == res.header('content-type')
        assert content == res.body
        assert content == app.content  # this is cashed
        lastmod = res.header('last-modified')
        print "updating", tempfile
        file = open(tempfile,"a+")
        file.write("0123456789")
        file.close()
        res = TestApp(app).get("/",headers={'Cache-Control': 'max-age=0'})
        assert len(content)+10 == int(res.header('content-length'))
        assert 'text/plain' == res.header('content-type')
        assert content + "0123456789" == res.body
        assert app.content # we are still cached
        file = open(tempfile,"a+")
        file.write("X" * fileapp.CACHE_SIZE) # exceed the cashe size
        file.write("YZ")
        file.close()
        res = TestApp(app).get("/",headers={'Cache-Control': 'max-age=0'})
        newsize = fileapp.CACHE_SIZE + len(content)+12
        assert newsize == int(res.header('content-length'))
        assert newsize == len(res.body)
        assert res.body.startswith(content) and res.body.endswith('XYZ')
        assert not app.content # we are no longer cached
    finally:
        import os
        os.unlink(tempfile)

def _excercize_range(build,content):
    res = build("bytes=0-%d" % (len(content)-1))
    assert res.header('accept-ranges') == 'bytes'
    assert res.body == content
    assert res.header('content-length') == str(len(content))
    res = build("bytes=-%d" % (len(content)-1))
    assert res.body == content
    assert res.header('content-length') == str(len(content))
    res = build("bytes=0-")
    assert res.body == content
    assert res.header('content-length') == str(len(content))
    res = build("bytes=0-9")
    assert res.body == content[:10]
    assert res.header('content-length') == '10'
    res = build("bytes=%d-" % (len(content)-1))
    assert res.body == 'Z'
    assert res.header('content-length') == '1'
    res = build("bytes=%d-%d" % (3,17))
    assert res.body == content[3:18]
    assert res.header('content-length') == '15'

def test_range():
    content = string.letters * 5
    def build(range):
        app = DataApp(content)
        return TestApp(app).get("/",headers={'Range': range})
    _excercize_range(build,content)

def test_file_range():
    from paste import fileapp
    import random, string, os
    tempfile = "test_fileapp.%s.txt" % (random.random())
    content = string.letters * (1+(fileapp.CACHE_SIZE / len(string.letters)))
    assert len(content) > fileapp.CACHE_SIZE
    file = open(tempfile,"w")
    file.write(content)
    file.close()
    try:
        def build(range):
            app = fileapp.FileApp(tempfile)
            return TestApp(app).get("/",headers={'Range': range})
        _excercize_range(build,content)
        for size in (13,len(string.letters),len(string.letters)-1):
            fileapp.BLOCK_SIZE = size
            _excercize_range(build,content)
    finally:
        import os
        os.unlink(tempfile)