import os,sys,json,threading,unittest,urllib.request,urllib.error,types
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','scripts'))
try:import websockets  # noqa
except ImportError:sys.modules['websockets']=types.ModuleType('websockets')
import bridge

class Fake:
    cdp=1;model='fake-model';mc=0
    def new_chat(s):return{'status':'ok'}

class BridgeHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(c):
        bridge.b=Fake()
        c.srv=bridge.ThreadedHTTPServer(('127.0.0.1',0),bridge.H)
        c.base='http://127.0.0.1:%d'%c.srv.server_address[1]
        threading.Thread(target=c.srv.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(c):c.srv.shutdown();c.srv.server_close()
    def req(s,path,data=None):
        r=urllib.request.Request(s.base+path,data=data,method='POST' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(r,timeout=5) as x:return x.status,json.loads(x.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def test_new_empty_body(s):
        c,d=s.req('/new',b'');s.assertEqual(c,200);s.assertIsInstance(d,dict)
    def test_chat_invalid_json(s):
        c,d=s.req('/chat',b'{bad');s.assertEqual(c,400);s.assertEqual(d['status'],'error')
    def test_extract_bad_after(s):
        c,d=s.req('/extract?after=x');s.assertEqual(c,400);s.assertEqual(d['status'],'error')
    def test_models(s):
        c,d=s.req('/models');s.assertEqual(c,200);s.assertIsInstance(d['models'],list)

class CleanTest(unittest.TestCase):
    def test_clean(s):
        r=bridge.Bridge._clean(None,'Answer\nGood\nBad\n')
        s.assertNotIn('Good\nBad',r);s.assertIn('Answer',r)
        r=bridge.Bridge._clean(None,'Thought for 3s\nHello world this is text')
        s.assertNotIn('Thought for',r);s.assertIn('Hello world',r)

if __name__=='__main__':unittest.main()
