import json,asyncio,websockets,urllib.request,time,threading,re,argparse
from http.server import HTTPServer,BaseHTTPRequestHandler
MODELS=['Gemini 3.1 Pro (High)','Gemini 3.1 Pro (Low)','Gemini 3 Flash','Claude Sonnet 4.6 (Thinking)','Claude Opus 4.6 (Thinking)','GPT-OSS 120B (Medium)']
PREFIX='[Direct mode] Reply directly and concisely. No task boundaries, no artifacts, no planning mode.\n\n'
RELOAD_TIMEOUT=15  # seconds to wait for page ready after reload

class Bridge:
    def __init__(s,cdp=9229):
        s.cdp=cdp;s.lock=threading.Lock();s.model=None;s.mc=0;s.last_result=None;s.cdp_recovering=False
        s._start_watchdog()
    def _start_watchdog(s):
        def run():
            fails=0
            while True:
                time.sleep(60)
                try:
                    t=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{s.cdp}/json/list',timeout=5).read())
                    ok=any(x.get('title') in ('Antigravity','Task') or 'workbench.html' in x.get('url','') for x in t)
                    if ok:
                        if s.cdp_recovering:
                            try:
                                with s.lock:asyncio.run(s._reload())
                            except:pass
                            s.cdp_recovering=False
                        fails=0
                    else:fails+=1
                except:fails+=1
                if fails>=3 and not s.cdp_recovering:s.cdp_recovering=True;print('[WATCHDOG] CDP recovering',flush=True)
        threading.Thread(target=run,daemon=True).start()
    def _ws(s):
        last_err=None
        for i in range(3):
            try:
                t=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{s.cdp}/json/list',timeout=5).read())
                a=[x for x in t if x.get('title') in ('Antigravity','Task')]
                if not a:a=[x for x in t if 'workbench.html' in x.get('url','')]
                if not a:raise Exception('No Antigravity')
                return a[0]['webSocketDebuggerUrl']
            except Exception as e:
                last_err=e
                if i<2:time.sleep([2,4,8][i])
        raise last_err
    def chat(s,p,to=120,m=None):
        with s.lock:
            r=asyncio.run(s._chat(p,to,m))
            s.last_result=r
            return r
    def clear(s):
        with s.lock:s.mc=0;s.model=None
        return{'status':'ok'}
    def get_result(s):
        return s.last_result or{'status':'none'}
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
    async def _reload(s):
        """Reload Antigravity chat page with timeout guard — fixes hang bug"""
        try:
            async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
                mid=[0]
                await s._e(ws,mid,'location.reload()')
                await asyncio.sleep(2)
                ready=await s._wait_ready(ws,mid,timeout=RELOAD_TIMEOUT)
                s.mc=0
                return{'status':'ok','method':'reload','ready':ready}
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
                if result.get('status') in ('high_traffic','agent_error'):
                    fb=FALLBACK_CHAIN.get(model or s.model or '')
                    if fb:print(f'[FALLBACK] -> {fb}',flush=True);model=fb;continue
                    return result
                # error => reload and retry (with timeout guard)
                if attempt<2:
                    try:
                        async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
                            mid=[0]
                            await s._e(ws,mid,'location.reload()')
                            await asyncio.sleep(2)
                            await s._wait_ready(ws,mid,timeout=RELOAD_TIMEOUT)
                            s.mc=0
                    except Exception:pass
                    continue
                return result
            except Exception as e:
                if attempt<2:await asyncio.sleep(2);continue
                return{'error':str(e),'status':'error'}
        return{'error':'max retries','status':'error'}
    async def _do_chat(s,prompt,timeout,model):
        async with websockets.connect(s._ws(),max_size=10*1024*1024,open_timeout=10) as ws:
            mid=[0];ev=lambda js:s._e(ws,mid,js)
            # Wait for page ready
            if not await s._wait_ready(ws,mid,timeout=10):
                return{'error':'page not ready','status':'error'}
            # Switch model
            if model and model!=s.model:
                await ev(r"""(()=>{const ss=document.querySelectorAll('span');for(const x of ss){if(x.className.includes('select-none')&&x.className.includes('min-w-0')){const p=x.parentElement;if(p){p.click();return'OK'}}}return'NO'})()""")
                await asyncio.sleep(0.8)
                safe=model.replace("'","\\'")
                await ev(f"""(()=>{{const a=document.querySelectorAll('*');for(const e of a){{if(e.childElementCount===0&&e.textContent.trim()==='{safe}'){{let t=e;for(let i=0;i<5;i++){{const c=(t.className||'');if(c.includes('cursor-pointer')||c.includes('hover:')||c.includes('px-2')){{t.click();return'OK'}}t=t.parentElement;if(!t)break}}e.click();return'OK'}}}}return'NO'}})()""")
                await asyncio.sleep(0.5);s.model=model
            # Auto reload every 10 msgs (with timeout guard)
            s.mc+=1
            if s.mc>10:
                try:
                    await ev('location.reload()')
                    await asyncio.sleep(2)
                    await s._wait_ready(ws,mid,timeout=RELOAD_TIMEOUT)
                except Exception:pass
                s.mc=1
                return await s._do_chat(prompt,timeout,model)
            # Full prompt
            full=PREFIX+prompt
            safe=full.replace('\\','\\\\').replace("'","\\'")
            safe=safe.replace('\n','\\n').replace('\r','')
            r=await ev(f"""(()=>{{const d=document.querySelector('div[role="textbox"][contenteditable="true"]');if(!d)return'NO';d.focus();d.textContent='';document.execCommand('insertText',false,'{safe}');return'OK'}})()""")
            if str(r)!='OK':return{'error':f'type:{r}','status':'error'}
            await asyncio.sleep(0.3)
            # 优先找 Send 按钮，找不到就用 Enter 键发送
            r=await ev("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Send');if(b&&!b.disabled){b.click();return'OK_BTN';}return'NO';})()""")
            if 'OK' not in str(r):
                # 用 Enter 键发送（Antigravity 支持 Enter 发送）
                r=await ev("""(()=>{const d=document.querySelector('div[role="textbox"][contenteditable="true"]');if(!d)return'NO_INPUT';d.focus();const e=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,bubbles:true});d.dispatchEvent(e);return'OK_ENTER';})()""")
            if 'OK' not in str(r):return{'error':f'send:{r}','status':'error'}
            # Poll
            start=time.time();marker=prompt[:60]
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
        if s.path=='/clear':s._j(200,b.clear());return
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
        elif s.path=='/new':
            try:s._j(200,b.new_chat())
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        else:s.send_response(404);s.end_headers()
    def do_GET(s):
        if s.path=='/result':s._j(200,b.get_result())
        elif s.path=='/health':
            try:
                t=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{b.cdp}/json/list',timeout=5).read())
                ok=any(x.get('title') in ('Antigravity','Task') or 'workbench.html' in x.get('url','') for x in t)
                s._j(200,{'status':'cdp_recovering' if b.cdp_recovering else ('ok' if ok else 'no_target'),'model':b.model,'msgs':b.mc,'version':'v12'})
            except:s._j(200,{'status':'cdp_down'})
        elif s.path=='/models':s._j(200,{'models':MODELS,'current':b.model})
        elif s.path=='/imgcount':
            # 不需要加锁，只读 DOM
            try:
                result=asyncio.run(b._get_img_count())
                s._j(200,result)
            except Exception as e:s._j(500,{'error':str(e),'status':'error'})
        elif s.path.startswith('/extract'):
            # 提取最新生成的图片（不加锁，避免和 /chat 死锁）
            from urllib.parse import urlparse,parse_qs
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
if __name__=='__main__':
    pa=argparse.ArgumentParser();pa.add_argument('--port',type=int,default=19999);pa.add_argument('--cdp-port',type=int,default=9229)
    a=pa.parse_args();b=Bridge(a.cdp_port)
    print(f'AG Bridge v11 :{a.port}',flush=True)
    ThreadedHTTPServer(('0.0.0.0',a.port),H).serve_forever()
