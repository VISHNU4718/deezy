import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ArrowUp, Plus, MessageSquare, CheckSquare, Bookmark, FileText, Settings, Clock, Download, Mic, Volume2, X, Check, ChevronRight, ExternalLink } from 'lucide-react';

type State = { revision: number; files: Record<string,string>; tasks: {id:string;title:string;done:boolean}[]; memories:string[]; applied:string[] };
type Event = {tool:string;status:string;summary:string;result?:unknown};
type Action = {id:string;tool:string;arguments:Record<string,string>};
type Result = {mode:string;message:string;actions:Action[];events:Event[];sources:{title:string;url:string}[];base_revision:number;usage?:{input_tokens?:number;output_tokens?:number};latency_ms?:number;model?:string};
type Message = {id:string;role:'user'|'assistant';text:string;result?:Result;resolved?:boolean};
type Conversation = {id:string;title:string;messages:Message[]};
type Store = {workspace:State;conversations:Conversation[];active:string;activity:{id:string;objective:string;status:string;time:string;events:Event[]}[]};
type Status = {ai_ready:boolean;model:string;web_search:boolean;reason:string};
const KEY='deezy-workspace-v2';
const emptyState=():State=>({revision:0,files:{},tasks:[],memories:[],applied:[]});
const id=()=>crypto.randomUUID();
const fresh=():Store=>{const c={id:id(),title:'New conversation',messages:[]};return {workspace:emptyState(),conversations:[c],active:c.id,activity:[]};};

function load():Store {
  try { const data=JSON.parse(localStorage.getItem(KEY)||'null');
    if(data && Array.isArray(data.conversations) && data.conversations.length && data.workspace?.files && Array.isArray(data.workspace.tasks) && Array.isArray(data.workspace.memories) && Array.isArray(data.activity)) return data;
  } catch { /* A fresh workspace is still usable when storage is unavailable. */ }
  return fresh();
}
async function api(path:string, body?:unknown, signal?:AbortSignal) {
  const r=await fetch('/api/assistant/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal});
  const data=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:'This request could not be completed. Nothing changed.');
  return data;
}
function download(name:string,content:string,type='text/plain') {
  const url=URL.createObjectURL(new Blob([content],{type})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function Text({text}:{text:string}) {
  const pieces=text.split(/(\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g);
  return <div className="answer-text">{pieces.map((p,i)=>{const m=p.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);return m?<a key={i} href={m[2]} target="_blank" rel="noopener noreferrer">{m[1]}</a>:<React.Fragment key={i}>{p}</React.Fragment>;})}</div>;
}
const labels:Record<string,string>={write_file:'Save file',add_task:'Add task',complete_task:'Complete task',save_memory:'Remember preference',read_file:'Read file',list_files:'List files',list_tasks:'List tasks',current_time:'Check time',web_search:'Search the web'};
function Trace({events}:{events:Event[]}) {
  if(!events?.length)return null;
  return <details className="trace"><summary>{events.length} execution {events.length===1?'step':'steps'}<ChevronRight size={13}/></summary><ol>{events.map((e,i)=><li key={i}><div><span className={'step-dot '+e.status}/><strong>{labels[e.tool]||e.tool}</strong><span>{e.status}</span></div><p>{e.summary}</p>{e.result!==undefined&&<details><summary>Inspect result</summary><pre>{JSON.stringify(e.result,null,2)}</pre></details>}</li>)}</ol></details>;
}

export default function Workspace() {
  const [store,setStore]=useState<Store>(load);const latest=useRef(store);latest.current=store;
  const [status,setStatus]=useState<Status|null>(null),[statusError,setStatusError]=useState('');
  const [draft,setDraft]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[storageError,setStorageError]=useState('');
  const [note,setNote]=useState(''),[task,setTask]=useState(''),[filename,setFilename]=useState(''),[filetext,setFiletext]=useState('');
  const [listening,setListening]=useState(false);const recognition=useRef<any>(null);const abort=useRef<AbortController|null>(null);
  const location=useLocation(),navigate=useNavigate(),end=useRef<HTMLDivElement>(null),input=useRef<HTMLTextAreaElement>(null);
  const page=location.pathname.split('/')[1]||'assistant';
  const conversation=store.conversations.find(c=>c.id===store.active)||store.conversations[0];
  const state=store.workspace;

  useEffect(()=>{try {localStorage.setItem(KEY,JSON.stringify(store));setStorageError('');}catch{setStorageError('This browser could not save your workspace. Export a copy before leaving.');}},[store]);
  useEffect(()=>{api('status').then(setStatus).catch(()=>setStatusError('Connection status is unavailable.'));},[]);
  useEffect(()=>{if(page==='assistant'||page==='chat')end.current?.scrollIntoView({behavior:'auto',block:'end'});},[conversation.messages.length,busy,page]);
  useEffect(()=>()=>{recognition.current?.stop();abort.current?.abort();},[]);

  function newChat(){const c={id:id(),title:'New conversation',messages:[]};setStore(s=>({...s,active:c.id,conversations:[c,...s.conversations].slice(0,30)}));setDraft('');setError('');navigate('/');}
  function updateWorkspace(next:State){setStore(s=>({...s,workspace:{...next,revision:s.workspace.revision+1}}));}
  function addMessage(cid:string,message:Message){setStore(s=>({...s,conversations:s.conversations.map(c=>c.id===cid?{...c,messages:[...c.messages,message].slice(-100)}:c)}));}

  async function send(text:string){
    text=text.trim();if(!text||busy)return;setBusy(true);setError('');setDraft('');
    const cid=conversation.id,runId=id();const history=conversation.messages.slice(-12).map(m=>({role:m.role,content:m.text.slice(0,6000)}));
    addMessage(cid,{id:id(),role:'user',text});
    setStore(s=>({...s,conversations:s.conversations.map(c=>c.id===cid&&c.title==='New conversation'?{...c,title:text.slice(0,45)}:c)}));
    abort.current=new AbortController();
    try {
      const result:Result=await api('respond',{message:text,history,workspace:latest.current.workspace,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone},abort.current.signal);
      addMessage(cid,{id:runId,role:'assistant',text:result.message,result});
      setStore(s=>({...s,activity:[{id:runId,objective:text,status:result.actions.length?'Awaiting approval':result.events.some(e=>e.status==='failed')?'Needs attention':!result.events.length&&result.mode==='tools_only'?'Needs model':result.events.length?'Completed':'Answered',time:new Date().toISOString(),events:result.events},...s.activity].slice(0,100)}));
    } catch(e:any){setError(e.name==='AbortError'?'Stopped waiting. No workspace changes were applied.':e.message||'Could not reach Deezy. Your message is still in the conversation.');}
    finally{setBusy(false);abort.current=null;}
  }
  async function resolve(message:Message,approved:boolean){
    if(busy||!message.result)return;setBusy(true);setError('');
    try{
      const r=await api('approve',{approved,actions:message.result.actions,base_revision:message.result.base_revision,workspace:latest.current.workspace});
      setStore(s=>({...s,workspace:r.workspace,conversations:s.conversations.map(c=>({...c,messages:c.messages.map(m=>m.id===message.id?{...m,text:r.message,resolved:true,result:{...m.result!,actions:[],events:[...(m.result?.events||[]),...r.events]}}:m)})),activity:s.activity.map(a=>a.id===message.id?{...a,status:approved?'Approved and applied':'Declined',events:[...a.events,...r.events]}:a)}));
    }catch(e:any){setError(e.message);}finally{setBusy(false);}
  }
  function dictate(){
    if(listening){recognition.current?.stop();setListening(false);return;}
    const Speech=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
    if(!Speech){setError('Voice input is not supported in this browser. You can still type.');return;}
    const r=new Speech();r.lang=navigator.language||'en-US';r.interimResults=false;
    r.onresult=(e:any)=>{setDraft(d=>[d,e.results[0][0].transcript].filter(Boolean).join(' '));input.current?.focus();};
    r.onend=()=>setListening(false);r.onerror=()=>{setListening(false);setError('Voice input could not start. Check microphone permission or type instead.');};
    recognition.current=r;r.start();setListening(true);
  }
  const nav=[{to:'/',label:'Assistant',Icon:MessageSquare},{to:'/tasks',label:'Tasks',Icon:CheckSquare},{to:'/memory',label:'Memory',Icon:Bookmark},{to:'/files',label:'Files',Icon:FileText},{to:'/history',label:'Activity',Icon:Clock},{to:'/settings',label:'Settings',Icon:Settings}];
  const isChat=page==='assistant'||page==='chat';
  return <div className={"workspace-shell "+(!conversation.messages.length&&isChat?"is-empty":"")}>
    <a className="skip" href="#workspace-main">Skip to content</a>
    <aside className="sidebar"><a className="wordmark" href="/" aria-label="Deezy home">Deezy</a>
      <button className="new-chat" onClick={newChat}><Plus size={16}/>New chat</button>
      <nav aria-label="Workspace">{nav.map(({to,label,Icon})=><NavLink key={to} to={to} end={to==='/'}><Icon size={17}/>{label}{label==='Tasks'&&state.tasks.filter(t=>!t.done).length>0&&<span className="nav-count">{state.tasks.filter(t=>!t.done).length}</span>}</NavLink>)}</nav>
      <div className="recent"><p className="eyebrow">Your chats</p>{store.conversations.slice(0,7).map(c=><button key={c.id} className={c.id===store.active?'selected':''} onClick={()=>{setStore(s=>({...s,active:c.id}));navigate('/');}} title={c.title}>{c.title}</button>)}</div>
      <div className="sidebar-foot"><span className="local-dot"/>Browser workspace<span>Chats and files stay on this device</span></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div><span className="mobile-brand">deezy / </span>{isChat?'Deezy':nav.find(n=>n.to==='/'+page)?.label||'Workspace'}</div><NavLink to="/settings" className={'connection '+(status?.ai_ready?'ready':'')}><span/>{status?.ai_ready?'OpenAI connected':statusError?'Connection unavailable':status?'Tools only · connect OpenAI':'Checking connection'}</NavLink></header>
      <main id="workspace-main" tabIndex={-1} className={'main-content '+(isChat?'chat-content':'')}>
        {(error||storageError)&&<div className="notice error" role="alert">{error||storageError}<button aria-label="Dismiss error" onClick={()=>{setError('');setStorageError('');}}><X size={15}/></button></div>}
        {isChat?<>
          <div className="conversation">
            {!conversation.messages.length?<section className="welcome"><h1>What can I help with?</h1>
              {!status?.ai_ready&&status&&<div className="connection-note">AI isn't connected. You can still create notes and tasks. <NavLink to="/settings">Connection details <ChevronRight size={13}/></NavLink></div>}
              <div className="starters">{[{tag:'RESEARCH',text:'Compare approaches to persistent memory for a personal assistant.',hint:status?.ai_ready&&status.web_search?'Find sources and compare tradeoffs':'Needs OpenAI and web search enabled',disabled:!status?.ai_ready||!status.web_search},{tag:'TASKS',text:'Add task Prepare a project walkthrough',hint:'Preview a change, then approve it'},{tag:'FILES',text:'Create file project-notes.md: # Project notes\n\n## What works\n\n## What to test next',hint:'Create a real workspace file'}].map(s=><button key={s.tag} disabled={s.disabled} onClick={()=>send(s.text)}><strong>{s.tag==='RESEARCH'?'Research a question':s.tag==='TASKS'?'Make a task':'Create a working note'}</strong></button>)}</div>
            </section>:conversation.messages.map(m=><article key={m.id} className={'message '+m.role}><div className="message-label">{m.role==='user'?'You':'Deezy'}{m.role==='assistant'&&m.result&&<span>{m.result.mode==='ai'?'OpenAI':'Direct tool command'}</span>}</div><Text text={m.text}/>
              {!!m.result?.sources.length&&<div className="sources"><span className="eyebrow">SOURCES</span>{m.result.sources.map(s=><a href={s.url} key={s.url} target="_blank" rel="noopener noreferrer">{s.title}<ExternalLink size={12}/></a>)}</div>}
              {!!m.result?.actions.length&&!m.resolved&&<section className="approval"><div className="approval-heading"><span className="pending-dot"/>APPROVAL NEEDED<span>Nothing changed yet</span></div>{m.result.actions.map(a=><div className="proposal" key={a.id}><h3>{labels[a.tool]||a.tool}</h3>{Object.entries(a.arguments).map(([k,v])=><div key={k}><span className="field-label">{k}</span><pre>{v}</pre></div>)}{a.tool==='write_file'&&state.files[a.arguments.name]!==undefined&&<details><summary>Current file contents</summary><pre>{state.files[a.arguments.name]}</pre></details>}</div>)}<div className="approval-actions"><button className="primary" disabled={busy} onClick={()=>resolve(m,true)}><Check size={15}/>Approve changes</button><button className="secondary" disabled={busy} onClick={()=>resolve(m,false)}>Decline</button></div></section>}
              {m.result&&<Trace events={m.result.events}/>}
              {m.role==='assistant'&&<div className="message-foot">{m.result?.latency_ms?`${(m.result.latency_ms/1000).toFixed(1)}s · ${m.result.usage?.input_tokens||0} input / ${m.result.usage?.output_tokens||0} output tokens`:null}{'speechSynthesis' in window&&<button aria-label="Read response aloud" title="Read aloud" onClick={()=>{speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(m.text));}}><Volume2 size={14}/></button>}</div>}
            </article>)}
            {busy&&<p className="working" role="status"><span/>Working on it… {abort.current&&<button onClick={()=>abort.current?.abort()}>Stop waiting</button>}</p>}<div ref={end}/>
          </div>
          <div className="composer-wrap"><form className="composer" onSubmit={e=>{e.preventDefault();send(draft);}}><label className="sr-only" htmlFor="message">Message Deezy</label><textarea id="message" ref={input} value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Message Deezy" maxLength={4000} rows={2} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send(draft);}}}/><div className="composer-actions"><span>{listening?'Listening — review the text before sending':`${state.memories.length} saved preferences · ${Object.keys(state.files).length} files`}</span><button type="button" onClick={dictate} className={listening?'listening':''} aria-label={listening?'Stop dictation':'Dictate a message'}><Mic size={18}/></button><button className="send" disabled={busy||!draft.trim()} aria-label="Send message"><ArrowUp size={18}/></button></div></form><p className="composer-hint">Deezy can make mistakes. Review proposed changes before approving.</p></div>
        </>:page==='tasks'?<div className="page"><h1>Tasks</h1><p className="intro">A short list of what you intend to do. These are to-do items, not scheduled reminders.</p><form className="inline-form" onSubmit={e=>{e.preventDefault();if(task.trim()&&state.tasks.length<100){updateWorkspace({...state,tasks:[...state.tasks,{id:id(),title:task.trim(),done:false}]});setTask('');}}}><label className="sr-only" htmlFor="task">New task</label><input id="task" value={task} onChange={e=>setTask(e.target.value)} maxLength={200} placeholder="What needs doing?"/><button className="primary" disabled={!task.trim()||busy}><Plus size={16}/>Add task</button></form><div className="item-list">{!state.tasks.length?<div className="empty"><CheckSquare size={24}/><h2>No tasks yet.</h2><p>Add one here, or ask Deezy to prepare a task for approval.</p></div>:state.tasks.map(t=><div className={'task-row '+(t.done?'done':'')} key={t.id}><label><input type="checkbox" checked={t.done} onChange={()=>updateWorkspace({...state,tasks:state.tasks.map(x=>x.id===t.id?{...x,done:!x.done}:x)})}/><span>{t.title}</span></label><button aria-label={'Remove task '+t.title} onClick={()=>updateWorkspace({...state,tasks:state.tasks.filter(x=>x.id!==t.id)})}><X size={15}/></button></div>)}</div></div>:
          page==='memory'?<div className="page"><h1>Memory</h1><p className="intro">Preferences you've explicitly saved. Deezy receives these as context when you use the connected model. Nothing is inferred or saved automatically.</p><form className="inline-form" onSubmit={e=>{e.preventDefault();if(note.trim()&&state.memories.length<30){updateWorkspace({...state,memories:[...state.memories,note.trim()]});setNote('');}}}><label className="sr-only" htmlFor="memory">Preference to remember</label><input id="memory" value={note} onChange={e=>setNote(e.target.value)} maxLength={500} placeholder="For example: keep explanations concise"/><button className="primary" disabled={!note.trim()||busy}><Plus size={16}/>Save preference</button></form>{!state.memories.length?<div className="empty"><Bookmark size={24}/><h2>Nothing remembered yet.</h2><p>Save a preference here, or say “Remember …” in the assistant.</p></div>:<div className="memory-list">{state.memories.map((m,i)=><article key={i}><Bookmark size={16}/><p>{m}</p><button aria-label={'Remove preference '+(i+1)} onClick={()=>updateWorkspace({...state,memories:state.memories.filter((_,n)=>n!==i)})}><X size={15}/></button></article>)}</div>}</div>:
          page==='files'?<div className="page"><h1>Files</h1><p className="intro">Text files in your browser workspace. Deezy can read and propose edits to these files; it cannot browse your computer.</p><form className="file-form" onSubmit={e=>{e.preventDefault();if(!/^[A-Za-z0-9][A-Za-z0-9_. -]{0,79}$/.test(filename)||!filetext.trim()){setError('Use a simple filename such as notes.md and add some content.');return;}if(Object.keys(state.files).length>=20&&!state.files[filename]){setError('This workspace can hold 20 files. Export or remove one first.');return;}const files={...state.files,[filename]:filetext};if(Object.values(files).reduce((total,text)=>total+text.length,0)>100000){setError('The workspace can hold 100,000 characters. Export or remove a file first.');return;}updateWorkspace({...state,files});setFilename('');setFiletext('');}}><label htmlFor="filename">File name</label><input id="filename" value={filename} onChange={e=>setFilename(e.target.value)} placeholder="notes.md" maxLength={80}/><label htmlFor="file-content">Contents</label><textarea id="file-content" value={filetext} onChange={e=>setFiletext(e.target.value)} rows={4} maxLength={24000} placeholder="A brief, draft, or notes you want to work with."/><button className="primary" disabled={busy||!filename||!filetext}>Save file</button></form>{!Object.keys(state.files).length?<p className="muted">No files yet. You can also ask Deezy to create one.</p>:Object.entries(state.files).map(([name,content])=><details className="file-card" key={name}><summary><FileText size={17}/>{name}<span>{content.length.toLocaleString()} characters</span></summary><pre>{content}</pre><div className="file-buttons"><button className="secondary" onClick={()=>download(name,content)}><Download size={15}/>Download</button><button className="secondary" onClick={()=>{setFilename(name);setFiletext(content);window.scrollTo({top:0,behavior:'smooth'});}}>Edit</button><button className="text-button" onClick={()=>{const files={...state.files};delete files[name];updateWorkspace({...state,files});}}>Remove</button></div></details>)}</div>:
          page==='history'?<div className="page"><h1>Activity</h1><p className="intro">Requests, approvals and execution results from this browser.</p>{!store.activity.length?<div className="empty"><Clock size={24}/><h2>No activity yet.</h2><p>Completed requests and pending approvals appear here.</p></div>:store.activity.map(a=><article className="activity-card" key={a.id}><div><span className="status-label">{a.status}</span><time>{new Date(a.time).toLocaleString()}</time></div><h2>{a.objective}</h2><Trace events={a.events}/></article>)}</div>:
          <div className="page settings-page"><h1>Settings</h1><p className="intro">The model connection is managed by the server. Your workspace stays with your browser.</p><section className="settings-section"><h2>OpenAI connection</h2><div className="setting-row"><span>Status</span><strong>{status?.ai_ready?'Connected':status?'Not connected':statusError||'Checking…'}</strong></div><div className="setting-row"><span>Model</span><code>{status?.model||'—'}</code></div><div className="setting-row"><span>Live web research</span><strong>{status?.ai_ready&&status.web_search?'Enabled':'Not enabled'}</strong></div>{!status?.ai_ready&&<p className="muted">Without a connection, Deezy supports direct task, memory and file commands. It does not simulate AI answers or pretend to search the web.</p>}<a className="doc-link" href="https://github.com/VISHNU4718/deezy#openai-setup" target="_blank" rel="noopener noreferrer">Owner setup guide <ExternalLink size={13}/></a><button className="secondary" onClick={()=>{setStatusError('');api('status').then(setStatus).catch(()=>setStatusError('Connection status is unavailable.'));}}>Recheck connection</button></section><section className="settings-section"><h2>Storage &amp; privacy</h2><p>Conversations, tasks, files and saved preferences persist in this browser's local storage. They are not synced across devices. Clearing browser data removes them.</p><p>When the model is connected, your messages, recent conversation and saved preferences are sent to OpenAI. File content is sent when a file-reading tool uses it. Requests use <code>store: false</code>; that is not a promise of zero provider retention.</p><p>Voice dictation uses your browser's speech service and is reviewed before sending. Read-aloud uses the browser's voice.</p><button className="secondary" onClick={()=>download('deezy-workspace.json',JSON.stringify(state,null,2),'application/json')}><Download size={15}/>Export workspace</button></section><section className="settings-section"><h2>What Deezy can change</h2><p>Files, tasks and preferences in this workspace. Every model-proposed change needs approval. Deezy cannot operate your computer, send messages, buy anything or schedule notifications.</p></section><section className="settings-section"><h2>About this build</h2><p>Deezy 02 · A personal assistant for research, planning and workspace tasks. Built by Beernelli Vishnu Vardhan.</p><a className="doc-link" href="https://github.com/VISHNU4718/deezy" target="_blank" rel="noopener noreferrer">Source and evaluation notes <ExternalLink size={13}/></a></section></div>}
      </main>
    </div>
  </div>;
}

