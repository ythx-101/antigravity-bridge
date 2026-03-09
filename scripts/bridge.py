import json,asyncio,websockets,urllib.request,urllib.error,time,threading,re,argparse,uuid,sys
from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from collections import OrderedDict
# NOTE: Do NOT set Origin header for websockets — Electron rejects non-whitelisted origins
# but accepts connections with NO Origin header at all.
MODELS=['Gemini 3.1 Pro (High)','Gemini 3.1 Pro (Low)','Gemini 3 Flash','Claude Sonnet 4.6 (Thinking)','Claude Opus 4.6 (Thinking)','GPT-OSS 120B (Medium)']
PREFIX=''
RELOAD_TIMEOUT=15  # seconds to wait for page ready after reload

# --- Async task store ---
_tasks=OrderedDict();_tlock=threading.Lock();_TMAX=50
def _tadd(tid,kind):
    with _tlock:
        if len(_tasks)>=_TMAX:_tasks.popitem(last=False)
        _tasks[tid]={'id':tid,'kind':kind,'status':'running','result':None,'error':None,'created':time.time()}
def _tdone(tid,r):
    with _tlock:
        if tid in _tasks:_tasks[tid]['status']='ok';_tasks[tid]['result']=r
def _tfail(tid,e):
    with _tlock:
        if tid in _tasks:_tasks[tid]['status']='error';_tasks[tid]['error']=str(e)
def _tget(tid):
    with _tlock:return _tasks.get(tid)

class Bridge:
    def __init__(s,cdp=9229):s.cdp=cdp;s.lock=threading.Lock();s.model='Claude Opus 4.6 (Thinking)';s.mc=0
    def _ws(s):
        t=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{s.cdp}/json/list',timeout=5).read())
        # 优先匹配主 workbench（排除 Launchpad/jetski-agent 页面）
        a=[x for x in t if 'workbench.html' in x.get('url','') and 'jetski' not in x.get('url','')]
        if not a:a=[x for x in t if x.get('title') in ('Antigravity','Task')]
        if not a:a=[x for x in t if 'workbench' in x.get('url','')]
        if not a:raise Exception('No Antigravity')
        return a[0]['webSocketDebuggerUrl']
    def chat(s,p,to=300,m=None):
        with s.lock:return asyncio.run(s._chat(p,to,m))
    def switch(s,m):
        with s.lock:return asyncio.run(s._sw(m))
    def new_chat(s):
        with s.lock:return asyncio.run(s._reload())
    async def _e(s,ws,mid,js):
        mid[0]+=1;c=mid[0]
        await ws.send(json.dumps({'id':c,'method':'Runtime.evaluate','params':{'expression':js,'returnByValue':True,'awaitPromise':True}}))
        while True:
            r=json.loads(await asyncio.wait_for(ws.recv(),timeout=30))
            if r.get('id')==c:
                v=r.get('result',{}).get('result',{})
                return v.get('value',v.get('description',''))
    async def _wait_ready(s,ws,mid,timeout=20):
        """Wait for contenteditable input to appear = page ready; auto-dismiss popups"""
        start=time.time()
        while time.time()-start<timeout:
            try:
                # 自动点掉权限弹窗（Allow This Conversation / Allow Once）
                await s._e(ws,mid,"""(()=>{
                    const btns=[...document.querySelectorAll('button')];
                    const allow=btns.find(b=>b.textContent.trim()==='Allow This Conversation')||btns.find(b=>b.textContent.trim()==='Allow Once');
                    if(allow){allow.click();return'dismissed';}
                })()""")
                r=await s._e(ws,mid,"!!document.querySelector('div[contenteditable=\"true\"]')")
                if str(r)=='True':await asyncio.sleep(1);return True
            except Exception:pass
            await asyncio.sleep(0.5)
        return False
    async def _get_img_count(s):
        async with websockets.connect(s._ws(),max_size=1024*1024,open_timeout=5) as ws:
            mid=[0]
            n=await s._e(ws,mid,'document.querySelectorAll(\'img[alt="Generated image preview"]\').length')
            return{'count':int(str(n) or '0')}
    async def _extract_image(s,after_count=0):
        """从 DOM 提取最新生成图片，返回 base64。after_count: 只接受图片数量 > 此值时的图"""
        start=time.time()
        while time.time()-start<60:
            async with websockets.connect(s._ws(),max_size=50*1024*1024,open_timeout=10) as ws:
                mid=[0]
                count=await s._e(ws,mid,'document.querySelectorAll(\'img[alt="Generated image preview"]\').length')
                if int(str(count) or '0')>after_count:
                    b64=await s._e(ws,mid,'''(async()=>{
                        const imgs=document.querySelectorAll('img[alt="Generated image preview"]');
                        const img=imgs[imgs.length-1];
                        if(!img)return'';
                        try{
                            const resp=await fetch(img.src);
                            const blob=await resp.blob();
                            return new Promise(r=>{
                                const reader=new FileReader();
                                reader.onload=()=>r(reader.result.split(",")[1]);
                                reader.readAsDataURL(blob);
                            });
                        }catch(e){return'ERR:'+e.message;}
                    })()''')
                    if b64 and not str(b64).startswith('ERR'):
                        return{'status':'ok','image':b64,'count':count}
            await asyncio.sleep(3)
        return{'status':'error','error':'extract timeout'}
    async def _ssl_fix(s,ws,mid):
        """Enable Security domain + ignore self-signed SSL cert"""
        for method in ['Security.enable','Security.setIgnoreCertificateErrors']:
            mid[0]+=1;params={'ignore':True} if 'Ignore' in method else {}
            await ws.send(json.dumps({'id':mid[0],'method':method,'params':params}))
            try:await asyncio.wait_for(ws.recv(),timeout=3)
            except:pass
    async def _reload(s):
        """Reload Antigravity chat page — reconnects to new page after reload"""
        try:
            # Phase 1: trigger reload on current connection
            async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
                mid=[0]
                await s._ssl_fix(ws,mid)
                await s._e(ws,mid,'location.reload()')
            # Phase 2: wait for page to reload, then reconnect (page ID may change)
            await asyncio.sleep(3)
            for attempt in range(5):
                try:
                    async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws2:
                        mid2=[0]
                        await s._ssl_fix(ws2,mid2)
                        ready=await s._wait_ready(ws2,mid2,timeout=RELOAD_TIMEOUT)
                        s.mc=0
                        return{'status':'ok','method':'reload','ready':ready}
                except Exception:
                    await asyncio.sleep(2)
            return{'status':'error','error':'reload reconnect failed'}
        except asyncio.TimeoutError:
            return{'status':'error','error':'reload timeout'}
        except Exception as e:
            return{'status':'error','error':str(e)}
    async def _sw(s,name):
        async with websockets.connect(s._ws(),max_size=10*1024*1024) as ws:
            mid=[0]
            await s._e(ws,mid,r"""(()=>{const ss=document.querySelectorAll('span');for(const x of ss){if(x.className.includes('select-none')&&x.className.includes('min-w-0')){const p=x.parentElement;if(p){p.click();return'OK'}}}return'NO'})()""")
            await asyncio.sleep(0.8)
            safe=name.replace("'","\\'")
            r=await s._e(ws,mid,f"""(()=>{{const a=document.querySelectorAll('*');for(const e of a){{if(e.childElementCount===0&&e.textContent.trim()==='{safe}'){{let t=e;for(let i=0;i<5;i++){{const c=(t.className||'');if(c.includes('cursor-pointer')||c.includes('hover:')||c.includes('px-2')){{t.click();return'OK'}}t=t.parentElement;if(!t)break}}e.click();return'OK'}}}}return'NO'}})()""")
            await asyncio.sleep(0.5)
            if 'OK' in str(r):s.model=name;return{'status':'ok','model':name}
            return{'status':'error','error':f'Not found: {name}'}
    async def _chat(s,prompt,timeout,model):
        for attempt in range(3):
            try:
                result=await s._do_chat(prompt,timeout,model)
                if result.get('status')=='ok':return result
                if result.get('status')=='high_traffic':return result
                # error => reload and retry (with timeout guard)
                if attempt<2:
                    try:await s._reload()
                    except Exception:pass
                    continue
                return result
            except Exception as e:
                if attempt<2:await asyncio.sleep(2);continue
                return{'error':str(e),'status':'error'}
        return{'error':'max retries','status':'error'}
    async def _ensure_fast_mode(s,ws,mid):
        """确保切换到 Fast 模式，避免 Planning 模式卡死"""
        ev=lambda js:s._e(ws,mid,js)
        # 检查当前模式
        current=await ev("""(()=>{
            const btns=[...document.querySelectorAll('button')];
            const mode=btns.find(b=>b.textContent.trim()==='Fast'||b.textContent.trim()==='Planning');
            return mode?mode.textContent.trim():'';
        })()""")
        if str(current)=='Fast':return True
        # 点击模式按钮打开下拉
        await ev("""(()=>{
            const btns=[...document.querySelectorAll('button')];
            const mode=btns.find(b=>b.textContent.trim()==='Planning'||b.textContent.trim()==='Fast');
            if(mode){mode.click();return'OK';}
            return'NO';
        })()""")
        await asyncio.sleep(0.3)
        # 点击 Fast 选项
        r=await ev("""(()=>{
            const items=[...document.querySelectorAll('*')];
            for(const e of items){
                if(e.textContent.trim()==='Fast'&&e.childElementCount===0){
                    e.click();return'OK';
                }
            }
            return'NO';
        })()""")
        await asyncio.sleep(0.3)
        return 'OK' in str(r)
    async def _do_chat(s,prompt,timeout,model):
        async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
            mid=[0];ev=lambda js:s._e(ws,mid,js)
            await s._ssl_fix(ws,mid)
            # Wait for page ready
            if not await s._wait_ready(ws,mid,timeout=10):
                return{'error':'page not ready','status':'error'}
            # Ensure Fast mode
            await s._ensure_fast_mode(ws,mid)
            # Switch model
            if model and model!=s.model:
                await ev(r"""(()=>{const ss=document.querySelectorAll('span');for(const x of ss){if(x.className.includes('select-none')&&x.className.includes('min-w-0')){const p=x.parentElement;if(p){p.click();return'OK'}}}return'NO'})()""")
                await asyncio.sleep(0.8)
                safe=model.replace("'","\\'")
                await ev(f"""(()=>{{const a=document.querySelectorAll('*');for(const e of a){{if(e.childElementCount===0&&e.textContent.trim()==='{safe}'){{let t=e;for(let i=0;i<5;i++){{const c=(t.className||'');if(c.includes('cursor-pointer')||c.includes('hover:')||c.includes('px-2')){{t.click();return'OK'}}t=t.parentElement;if(!t)break}}e.click();return'OK'}}}}return'NO'}})()""")
                await asyncio.sleep(0.5);s.model=model
            # Auto reload every 10 msgs — close current WS, reload, then recurse
            s.mc+=1
            if s.mc>10:
                try:await ev('location.reload()')
                except Exception:pass
                s.mc=1
                await asyncio.sleep(3)
                return await s._do_chat(prompt,timeout,model)
            # Full prompt
            full=PREFIX+prompt
            safe=full.replace('\\','\\\\').replace("'","\\'")
            safe=safe.replace('\n','\\n').replace('\r','')
            r=await ev(f"""(()=>{{const d=document.querySelector('div[role="textbox"][contenteditable="true"]')||document.querySelector('[data-lexical-editor="true"]');if(!d)return'NO';d.focus();document.execCommand('selectAll');document.execCommand('delete');document.execCommand('insertText',false,'{safe}');return'OK'}})()""")
            if str(r)!='OK':return{'error':f'type:{r}','status':'error'}
            await asyncio.sleep(0.3)
            # 优先找 Send 按钮，找不到就用 CDP Input.dispatchKeyEvent Enter
            r=await ev("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Send');if(b&&!b.disabled){b.click();return'OK_BTN';}return'NO';})()""")
            if 'OK' not in str(r):
                # CDP Input.dispatchKeyEvent — 比 JS KeyboardEvent 更底层，Lexical 能识别
                mid[0]+=1;await ws.send(json.dumps({'id':mid[0],'method':'Input.dispatchKeyEvent','params':{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':13}}))
                await asyncio.wait_for(ws.recv(),timeout=5)
                mid[0]+=1;await ws.send(json.dumps({'id':mid[0],'method':'Input.dispatchKeyEvent','params':{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':13}}))
                await asyncio.wait_for(ws.recv(),timeout=5)
                r='OK_CDP_ENTER'
            if 'OK' not in str(r):return{'error':f'send:{r}','status':'error'}
            # Poll
            start=time.time();marker=prompt[:60];planning_detected=False
            while time.time()-start<timeout:
                await asyncio.sleep(2)
                body=str(await ev('document.body.innerText'))
                parts=body.split(marker)
                if len(parts)<2:continue
                after=parts[-1]
                has_gen='Generating' in after
                has_done='Good\nBad' in after
                has_traffic='high traffic' in after
                has_err='Agent execution terminated' in after or 'Agent terminated' in after
                # 检测 Planning 模式
                has_planning='Planning' in body or 'Task' in body or 'Executing' in body
                if has_planning and not planning_detected:
                    planning_detected=True
                    # 尝试提取 Planning 结果
                    plan_text=await ev("""(()=>{
                        const els=[...document.querySelectorAll('*')];
                        for(const e of els){
                            const txt=e.textContent||'';
                            if((txt.includes('Planning')||txt.includes('Task'))&&txt.length>100){
                                return txt;
                            }
                        }
                        return'';
                    })()""")
                    if plan_text and len(str(plan_text))>50:
                        # 等待 Planning 完成
                        await asyncio.sleep(3)
                        continue
                    else:
                        # 无法提取，快速失败
                        return{'error':'Planning mode detected but cannot extract result','status':'planning_error','elapsed':round(time.time()-start,1)}
                if has_done and has_traffic:return{'response':'Server high traffic','elapsed':round(time.time()-start,1),'model':s.model or'?','status':'high_traffic'}
                if has_err and has_done:return{'error':'agent_error','status':'agent_error','elapsed':round(time.time()-start,1)}
                if has_done and not has_gen:
                    return{'response':s._clean(after,prompt),'elapsed':round(time.time()-start,1),'model':s.model or'?','status':'ok'}
            body=str(await ev('document.body.innerText'))
            parts=body.split(marker)
            after=parts[-1] if len(parts)>=2 else body
            return{'response':s._clean(after,prompt),'elapsed':round(time.time()-start,1),'model':s.model or'?','status':'timeout'}
    def _clean(s,after,prompt=''):
        raw=after
        for f in['\nAsk anything','\nPlanning\n','\nSend\n','\nSend']:
            i=raw.rfind(f)
            if i>0:raw=raw[:i];break
        for m in MODELS:raw=raw.replace('\n'+m,'')
        for m in['\nModel','\nNew']:raw=raw.replace(m,'')
        raw=re.sub(r'^Thought for [<\d]+s\n?','',raw,flags=re.MULTILINE)
        raw=re.sub(
            r'^(Planning|Executing|Verifying|Looking for|Reading|Writing|Creating|Editing|'
            r'Viewing|Searching|Researching|Defining|Formulating|Considering|Analyzing|'
            r'Processing|Initiating|Calculating|Refining|Delivering|Determining|'
            r'Identifying|Evaluating|Preparing|Checking)[\s:].*$',
            '',raw,flags=re.MULTILINE
        )
        for n in['CRITICAL INSTRUCTION 1:','CRITICAL INSTRUCTION 2:']:
            i=raw.find(n)
            if i>=0:
                j=raw.find('\n\n',i)
                raw=raw[:i]+(raw[j+2:] if j>=0 else '')
        raw=re.sub(r'\nGood\nBad\s*','',raw)
        raw=re.sub(r'\n{3,}','\n\n',raw)
        for n in['Agent terminated','See our troubleshooting','Dismiss\nCopy debug','Error\nOur servers','Error\nVerification Required','[Direct mode]']:
            i=raw.find(n)
            if i>=0:raw=raw[:i]
        lines=[l for l in raw.split('\n') if not (len(l.strip().split())<4 and l.strip().endswith('.') and l.strip()[0].isupper() and '\n' not in l.strip())]
        return '\n'.join(lines).strip()
b=None
class H(BaseHTTPRequestHandler):
    def do_POST(s):
        d=json.loads(s.rfile.read(int(s.headers.get('Content-Length',0))))
        if s.path=='/chat':
            p=d.get('prompt','');m=d.get('model');to=d.get('timeout',180)
            ts=time.strftime('%H:%M:%S');print(f'[{ts}] >> {p[:80]}',flush=True)
            try:
                r=b.chat(p,to,m);s._j(200,r)
                print(f'[{ts}] << [{r.get("status")}] {r.get("response",r.get("error",""))[:80]} ({r.get("elapsed",0)}s)',flush=True)
            except Exception as e:s._j(500,{'error':str(e),'status':'error'});print(f'[{ts}] !! {e}',flush=True)
        elif s.path=='/model':
            mn=d.get('model','')
            if mn not in MODELS:s._j(400,{'error':f'Unknown','status':'error'})
            else:
                try:s._j(200,b.switch(mn))
                except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        elif s.path=='/async':
            p=d.get('prompt','');m=d.get('model');to=d.get('timeout',600)
            tid=uuid.uuid4().hex[:12];_tadd(tid,'chat')
            ts=time.strftime('%H:%M:%S');print(f'[{ts}] >> [async:{tid}] {p[:80]}',flush=True)
            def _run():
                try:r=b.chat(p,to,m);_tdone(tid,r)
                except Exception as e:_tfail(tid,e)
            threading.Thread(target=_run,daemon=True).start()
            s._j(200,{'status':'accepted','task_id':tid})
        elif s.path=='/new':
            try:s._j(200,b.new_chat())
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        else:s.send_response(404);s.end_headers()
    def do_GET(s):
        if s.path=='/health':
            try:
                t=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{b.cdp}/json/list',timeout=5).read())
                ok=any(x.get('title') in ('Antigravity','Task') or 'workbench.html' in x.get('url','') for x in t)
                s._j(200,{'status':'ok' if ok else 'no_target','model':b.model,'msgs':b.mc,'version':'v16'})
            except:s._j(200,{'status':'cdp_down'})
        elif s.path=='/models':s._j(200,{'models':MODELS,'current':b.model})
        elif s.path=='/imgcount':
            # 不需要加锁，只读 DOM
            try:
                result=asyncio.run(b._get_img_count())
                s._j(200,result)
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        elif s.path=='/history':
            try:
                async def _h():
                    async with websockets.connect(b._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
                        mid=[0];body=str(await b._e(ws,mid,'document.body.innerText'))
                        return{'status':'ok','content':b._clean(body),'raw_length':len(body)}
                s._j(200,asyncio.run(_h()))
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        elif s.path.startswith('/task/'):
            tid=s.path.split('/task/',1)[1].strip('/')
            t=_tget(tid)
            if not t:s._j(404,{'error':'not found','status':'error'})
            else:s._j(200,t)
        elif s.path.startswith('/extract'):
            # 提取最新生成的图片（不加锁，避免和 /chat 死锁）
            qs=parse_qs(urlparse(s.path).query)
            after=int(qs.get('after',['0'])[0])
            try:
                result=asyncio.run(b._extract_image(after_count=after))
                s._j(200,result)
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        else:s.send_response(404);s.end_headers()
    def _j(s,c,d):s.send_response(c);s.send_header('Content-Type','application/json');s.end_headers();s.wfile.write(json.dumps(d).encode())
    def log_message(s,*a):pass
from socketserver import ThreadingMixIn
class ThreadedHTTPServer(ThreadingMixIn,HTTPServer):daemon_threads=True

def _existing_bridge_status(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None

if __name__=='__main__':
    pa=argparse.ArgumentParser();pa.add_argument('--port',type=int,default=19999);pa.add_argument('--cdp-port',type=int,default=9229)
    a=pa.parse_args();b=Bridge(a.cdp_port)
    print(f'AG Bridge v16 :{a.port}',flush=True)
    try:
        ThreadedHTTPServer(('0.0.0.0',a.port),H).serve_forever()
    except OSError as e:
        if e.errno==98:
            print(f'Port {a.port} is already in use.',file=sys.stderr,flush=True)
            status=_existing_bridge_status(a.port)
            if status:
                print(f'Existing bridge health: {json.dumps(status)}',file=sys.stderr,flush=True)
                print('Use the running bridge, or stop it before starting a new one.',file=sys.stderr,flush=True)
            else:
                print('Another process is bound to that port. Stop it or choose a different --port.',file=sys.stderr,flush=True)
            sys.exit(1)
        raise
