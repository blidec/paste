import sys
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import types
import re
from py.test.collect import Module, PyCollector
from paste.util import thirdparty
doctest = thirdparty.load_new_module('doctest', (2, 4))
from paste import wsgilib
from paste import lint

class NoDefault:
    pass

class Dummy(object):

    def __init__(self, **kw):
        for name, value in kw.items():
            if name.startswith('method_'):
                name = name[len('method_'):]
                value = DummyMethod(value)
            setattr(self, name, value)

class DummyMethod(object):

    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self, *args, **kw):
        return self.return_value

class ParamCollector(PyCollector):

    def collect_function(self, extpy):
        if not extpy.check(func=1, basestarts='test_'):
            return
        func = extpy.resolve()
        if hasattr(func, 'params'):
            params = func.params
            for i, param in enumerate(params):
                item = self.Item(extpy, *param)
                item.name = item.name + '.%i' % i
                yield item
        else:
            yield self.Item(extpy)
    
class DoctestCollector(PyCollector):

    def __init__(self, extpy_or_module):
        if isinstance(extpy_or_module, types.ModuleType):
            self.module = extpy_or_module
            self.extpy = None
        else:
            self.extpy = extpy_or_module
            self.module = self.extpy.getpymodule()

    def __call__(self, extpy):
        # we throw it away, because this has been set up to explicitly
        # check another module; maybe this isn't clean
        if self.extpy is None:
            self.extpy = extpy
        return self

    def __iter__(self):
        finder = doctest.DocTestFinder()
        tests = finder.find(self.module)
        for t in tests:
            yield DoctestItem(self.extpy, t)

class DoctestItem(DoctestCollector.Item):

    def __init__(self, extpy, doctestitem, *args):
        self.extpy = extpy
        self.doctestitem = doctestitem
        self.name = extpy.basename
        self.args = args

    def execute(self, driver):
        runner = doctest.DocTestRunner()
        driver.setup_path(self.extpy)
        target, teardown = driver.setup_method(self.extpy)
        try:
            (failed, tried), run_output = capture_stdout(runner.run, self.doctestitem)
            if failed:
                raise self.Failed(msg=run_output, tbindex=-2)
                
        finally:
            if teardown:
                teardown(target)
                
def capture_stdout(func, *args, **kw):
    newstdout = StringIO()
    oldstdout = sys.stdout
    sys.stdout = newstdout
    try:
        result = func(*args, **kw)
    finally:
        sys.stdout = oldstdout
    return result, newstdout.getvalue()

def assert_error(func, *args, **kw):
    kw.setdefault('error', Exception)
    kw.setdefault('text_re', None)
    error = kw.pop('error')
    text_re = kw.pop('text_re')
    if text_re and isinstance(text_re, str):
        real_text_re = re.compile(text_re, re.S)
    else:
        real_text_re = text_re
    try:
        value = func(*args, **kw)
    except error, e:
        if real_text_re and not real_text_re.search(str(e)):
            assert False, (
                "Exception did not match pattern; exception:\n  %r;\n"
                "pattern:\n  %r"
                % (str(e), text_re))
    except Exception, e:
        assert False, (
            "Exception type %s should have been raised; got %s instead (%s)"
            % (error, e.__class__, e))
    else:
        assert False, (
            "Exception was expected, instead successfully returned %r"
            % (value))

def sorted(l):
    l = list(l)
    l.sort()
    return l


def fake_request(application, path_info='', use_lint=True, **environ):
    """
    Runs the application in a fake environment, returning a response object
    """
    if use_lint:
        application = lint.middleware(application)
    status, headers, body, errors = wsgilib.raw_interactive(
        application, path_info, **environ)
    res = FakeResponse(status, headers, body, errors)
    if res.errors:
        print 'Errors:'
        print res.errors
    return res

class FakeResponse(object):

    def __init__(self, status, headers, body, errors):
        self.status = status
        self.headers = headers
        self.body = body
        self.errors = errors

    def status_int__get(self):
        return int(self.status.split()[0])
    status_int = property(status_int__get)

    def all_ok(self):
        """
        Asserts that there were no errors and the status was 200 OK
        """
        assert not self.errors, (
            "Response had errors: %s" % self.errors)
        assert self.status_int == 200, (
            "Response did not return 200 OK: %r" % self.status)

    def header(self, name, default=NoDefault):
        """
        Returns the named header; an error if there is not exactly one
        matching header (unless you give a default -- always an error if
        there is more than one header)
        """
        found = None
        for cur_name, value in self.headers:
            if cur_name.lower() == name.lower():
                assert not found, (
                    "Ambiguous header: %s matches %r and %r"
                    % (name, found, value))
                found = value
        if found is None:
            if default is NoDefault:
                raise KeyError(
                    "No header found: %r (from %s)"
                    % (name, ', '.join([n for n, v in self.headers])))
            else:
                return default
        return found

    def all_headers(self, name):
        """
        Gets all headers, returns as a list
        """
        found = []
        for cur_name, value in self.headers:
            if cur_name.lower() == name.lower():
                found.append(value)
        return found

    def __contains__(self, s):
        return self.body.find(s) != -1
    
    def __repr__(self):
        return '<Response %s %r>' % (self.status, self.body[:20])

    def __str__(self):
        return 'Response: %s\n%s\n%s' % (
            self.status,
            '\n'.join(['%s: %s' % (n, v) for n, v in self.headers]),
            self.body)

class Dummy_smtplib(object):

    existing = None

    def __init__(self, server):
        assert not self.existing, (
            "smtplib.SMTP() called again before Dummy_smtplib.existing.reset() "
            "called.")
        self.server = server
        self.open = True
        self.__class__.existing = self

    def quit(self):
        assert self.open, (
            "Called %s.quit() twice" % self)
        self.open = False

    def sendmail(self, from_address, to_addresses, msg):
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.message = msg

    def install(cls):
        smtplib.SMTP = cls

    install = classmethod(install)

    def reset(self):
        assert not self.open, (
            "SMTP connection not quit")
        self.__class__.existing = None
        
class FakeFilesystem(object):

    def __init__(self):
        self.files = {}

    def make_file(self, filename, content):
        self.files[filename] = content

    def open(self, filename, mode='r'):
        if not self.files.has_key(filename):
            raise IOError("[FakeFS] No such file or directory: %r" % filename)


class FakeFile(object):

    def __init__(self, filename, content=None):
        self.filename = filename
        self.content = content

    def open(self, mode):
        if mode == 'r' or mode == 'rb':
            if self.content is None:
                raise IOError("[FakeFS] No such file or directory: %r" % filename)
            return ReaderFile(self)
        elif mode == 'w' or mode == 'wb':
            return WriterFile(self)
        else:
            assert 0, "Mode %r not yet implemented" % mode

class ReaderFile(object):

    def __init__(self, file):
        self.file = file
        self.stream = StringIO(self.file.content)
        self.open = True

    def read(self, *args):
        return self.stream.read(*args)

    def close(self):
        assert self.open, (
            "Closing open file")
        self.open = False

class WriterFile(object):

    def __init__(self, file):
        self.file = file
        self.stream = StringIO()
        self.open = True

    def write(self, arg):
        self.stream.write(arg)

    def close(self):
        assert self.open, (
            "Closing an open file")
        self.open = False
        
        
    
