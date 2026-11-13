import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, BarChart3, CalendarClock, CheckCircle2, ChevronDown, FileImage, RefreshCw, Save, ShieldCheck, Trash2, Upload} from 'lucide-react';
import './round3.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
async function api(path, options={}) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json().catch(() => ({detail: 'Unexpected server response'}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
function Pill({children, tone='neutral'}) { return <span className={`pill ${tone}`}>{children}</span>; }
function ErrorNote({message}) { return message ? <div className="r3-alert"><AlertTriangle size={16}/>{message}</div> : null; }

const EMPTY_EVIDENCE = {claim:'', source:'', source_url:'', owner:'', version:'1.0', valid_from:'', valid_until:'', status:'pending_verification'};
export function EvidenceRegistry() {
  const [records, setRecords] = useState([]);
  const [form, setForm] = useState(EMPTY_EVIDENCE);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [auditFor, setAuditFor] = useState(null); const [auditEvents, setAuditEvents] = useState([]);
  async function load() { try { setRecords(await api('/api/evidence')); setError(''); } catch (e) { setError(e.message); } }
  useEffect(() => { load(); }, []);
  function change(key, value) { setForm(current => ({...current, [key]:value})); }
  function edit(record) { setEditing(record.id); setForm({...record, status:['expired','scheduled'].includes(record.status) ? 'approved' : (record.source_status || record.status)}); setNotice(''); }
  function reset() { setEditing(null); setForm(EMPTY_EVIDENCE); }
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const payload = {...form};
      delete payload.id; delete payload.created_at; delete payload.updated_at; delete payload.source_status; delete payload.is_current;
      const result = await api(editing ? `/api/evidence/${editing}` : '/api/evidence', {method:editing?'PUT':'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      setNotice(`${result.id} ${editing?'updated':'created'}.`); reset(); await load();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function toggleAudit(id) {
    if (auditFor === id) { setAuditFor(null); setAuditEvents([]); return; }
    try { setAuditEvents(await api(`/api/evidence/${id}/history`)); setAuditFor(id); } catch(e) { setError(e.message); }
  }
  async function remove(id) {
    if (!window.confirm(`Delete evidence record ${id}? This cannot be undone.`)) return;
    setBusy(true); try { await api(`/api/evidence/${id}`, {method:'DELETE'}); setNotice(`${id} deleted.`); if (editing===id) reset(); await load(); } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  const active = records.filter(r=>r.status==='approved').length;
  const expired = records.filter(r=>r.status==='expired').length;
  const pending = records.filter(r=>r.status==='pending_verification').length;
  return <>
    <div className="page-head"><div><div className="eyebrow">ROUND 3 · EVIDENCE LIFECYCLE</div><h1>Evidence provenance registry</h1><p>Track where every approved statement came from, who owns it and when it stops being valid.</p></div><button className="outline" onClick={load}><RefreshCw size={16}/> Refresh</button></div>
    {error&&<ErrorNote message={error}/>} {notice&&<div className="r3-success"><CheckCircle2 size={16}/>{notice}</div>}
    <div className="r3-metrics"><div className="r3-metric"><small>Current approved</small><strong>{active}</strong></div><div className="r3-metric"><small>Expired</small><strong>{expired}</strong></div><div className="r3-metric"><small>Needs verification</small><strong>{pending}</strong></div><div className="r3-metric"><small>Total records</small><strong>{records.length}</strong></div></div>
    <div className="r3-columns"><section className="panel r3-form-panel"><div className="panel-head"><div><h2>{editing?'Edit evidence record':'Register evidence'}</h2><p>Approved records require a source, owner and validity metadata.</p></div>{editing&&<button className="text-btn" onClick={reset}>Cancel edit</button>}</div>
      <form onSubmit={save} className="r3-form">
        <label>Approved fact or policy <span>*</span><textarea rows={4} value={form.claim} onChange={e=>change('claim',e.target.value)} required minLength={5} placeholder="State the exact fact or rule this evidence supports."/></label>
        <div className="r3-two"><label>Source name <span>*</span><input value={form.source} onChange={e=>change('source',e.target.value)} required placeholder="Approved product facts v1.3"/></label><label>Source owner <span>*</span><input value={form.owner} onChange={e=>change('owner',e.target.value)} required placeholder="Brand team / Legal"/></label></div>
        <label>Source URL <input type="url" value={form.source_url} onChange={e=>change('source_url',e.target.value)} placeholder="https://... (optional)"/></label>
        <div className="r3-three"><label>Version<input value={form.version} onChange={e=>change('version',e.target.value)} placeholder="1.0"/></label><label>Valid from<input type="date" value={form.valid_from||''} onChange={e=>change('valid_from',e.target.value)}/></label><label>Valid until<input type="date" value={form.valid_until||''} onChange={e=>change('valid_until',e.target.value)}/></label></div>
        <label>Record state<select value={form.status} onChange={e=>change('status',e.target.value)}><option value="pending_verification">Pending verification</option><option value="approved">Approved</option><option value="archived">Archived</option></select></label>
        <button className="primary" disabled={busy}>{busy?'Saving...':<><Save size={16}/> {editing?'Save changes':'Add evidence record'}</>}</button>
      </form>
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Evidence inventory</h2><p>Expired or future-dated records are excluded from review evidence retrieval.</p></div></div>
      {records.length===0?<div className="empty">No evidence records yet.</div>:<div className="r3-record-list">{records.map(record=><article className="r3-record" key={record.id}><div className="r3-record-top"><div><b>{record.id}</b><Pill tone={record.status==='approved'?'green':record.status==='expired'?'red':record.status==='scheduled'?'blue':'amber'}>{record.status.replace('_',' ')}</Pill>{record.expires_soon&&<Pill tone="amber">Expires soon</Pill>}</div><div className="r3-record-actions"><button className="text-btn" onClick={()=>toggleAudit(record.id)}>Audit</button><button className="text-btn" onClick={()=>edit(record)}>Edit</button><button className="r3-icon-button" title="Delete evidence" onClick={()=>remove(record.id)}><Trash2 size={14}/></button></div></div><p>{record.claim}</p><small>{record.source} · Owner: {record.owner||'Unassigned'} · v{record.version||'1.0'}</small><small>Valid: {record.valid_from||'No start date'} → {record.valid_until||'No expiry'}</small>{record.source_url&&<a href={record.source_url} target="_blank" rel="noreferrer">Open source document</a>}{auditFor===record.id&&<div className="r3-evidence-audit">{auditEvents.length===0?<small>No audit events are available for this legacy record.</small>:auditEvents.map((event,index)=><div key={`${event.created_at}-${index}`}><b>{event.event.replace('_',' ')}</b><small>{event.detail}</small><small>{new Date(event.created_at).toLocaleString()}</small></div>)}</div>}</article>)}</div>}
    </section></div>
    <div className="r3-footnote"><CalendarClock size={16}/> Review engine only retrieves records currently marked approved and inside their validity window. Expiry dates are evaluated on the backend at request time.</div>
  </>;
}

export function VisualCompliance() {
  const [config, setConfig] = useState({palette:[], logo_reference_name:'', has_logo_reference:false});
  const [paletteText, setPaletteText] = useState('');
  const [logoFile, setLogoFile] = useState(null);
  const [creativeFile, setCreativeFile] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function load() { try { const [c,h] = await Promise.all([api('/api/visual/config'),api('/api/visual/reviews')]); setConfig(c); setPaletteText((c.palette||[]).join('\n')); setHistory(h); } catch(e) { setError(e.message); } }
  useEffect(() => { load(); }, []);
  async function savePalette(e) {
    e.preventDefault(); setBusy(true); setError(''); setNotice('');
    try { const palette = paletteText.split(/[\s,;]+/).map(x=>x.trim()).filter(Boolean); const c = await api('/api/visual/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({palette})}); setConfig(c); setPaletteText((c.palette||[]).join('\n')); setNotice('Approved brand palette saved.'); }
    catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function uploadLogo(e) {
    e.preventDefault(); if(!logoFile) return; setBusy(true); setError(''); setNotice('');
    try { const fd=new FormData(); fd.append('file',logoFile); const c=await api('/api/visual/logo-reference',{method:'POST',body:fd}); setConfig(c); setLogoFile(null); setNotice('Approved logo reference saved.'); }
    catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function removeLogo() {
    setBusy(true); try { const c=await api('/api/visual/logo-reference',{method:'DELETE'}); setConfig(c); setNotice('Logo reference removed.'); } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function analyse(e) {
    e.preventDefault(); if(!creativeFile) return; setBusy(true); setError(''); setNotice(''); setResult(null);
    try { const fd=new FormData(); fd.append('file',creativeFile); const data=await api('/api/visual/reviews',{method:'POST',body:fd}); setResult(data); setHistory(await api('/api/visual/reviews')); setNotice('Visual screening completed. Human confirmation is still required.'); }
    catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  return <>
    <div className="page-head"><div><div className="eyebrow">ROUND 3 · CREATIVE ASSET SCREENING</div><h1>Visual brand compliance</h1><p>Screen artwork for palette drift, possible logo mismatch and restricted text in images.</p></div><button className="outline" onClick={load}><RefreshCw size={16}/> Refresh</button></div>
    {error&&<ErrorNote message={error}/>} {notice&&<div className="r3-success"><CheckCircle2 size={16}/>{notice}</div>}
    <div className="r3-columns visual-config-grid"><section className="panel"><div className="panel-head"><div><h2>Approved brand palette</h2><p>Enter approved HEX values, one per line (up to 12).</p></div></div><form onSubmit={savePalette}><label>Brand colours</label><textarea rows={5} value={paletteText} onChange={e=>setPaletteText(e.target.value)} placeholder="#0B1F3A&#10;#16A6A1&#10;#F2B84B"/><div className="palette-preview">{config.palette?.map(c=><span key={c}><i style={{background:c}}/>{c}</span>)}</div><button className="primary" disabled={busy}><Save size={16}/> Save palette</button></form></section>
      <section className="panel"><div className="panel-head"><div><h2>Approved logo reference</h2><p>Upload an official logo file to enable similarity screening.</p></div><Pill tone={config.has_logo_reference?'green':'amber'}>{config.has_logo_reference?'Configured':'Not configured'}</Pill></div>{config.has_logo_reference&&<div className="r3-reference"><ShieldCheck size={18}/><span><b>{config.logo_reference_name}</b><small>Stored as the approved reference asset</small></span><button className="text-btn" onClick={removeLogo}>Remove</button></div>}<form onSubmit={uploadLogo}><label className="r3-file"><Upload size={18}/><span>{logoFile?.name||'Choose approved logo PNG, JPG or WebP'}</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setLogoFile(e.target.files?.[0]||null)}/></label><button className="outline" disabled={!logoFile||busy}>Save logo reference</button></form></section></div>
    <section className="panel r3-analyse-panel"><div className="panel-head"><div><h2>Screen a creative asset</h2><p>Upload a campaign visual, banner, social graphic or product creative (8 MB max).</p></div><Pill tone="blue">PNG · JPG · WebP</Pill></div><form className="r3-inline-form" onSubmit={analyse}><label className="r3-file"><FileImage size={20}/><span>{creativeFile?.name||'Choose creative image'}</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setCreativeFile(e.target.files?.[0]||null)}/></label><button className="primary" disabled={!creativeFile||busy}>{busy?'Analysing...':<><ShieldCheck size={16}/> Analyse asset</>}</button></form></section>
    {result&&<section className="panel"><div className="panel-head"><div><div className="eyebrow">VISUAL SCREENING RESULT · {result.id.slice(0,8)}</div><h2>{result.filename}</h2><p>{result.width} × {result.height}px · SHA-256 {result.sha256.slice(0,16)}…</p></div><Pill tone="amber">Human review required</Pill></div><div className="r3-colour-list">{result.dominant_colors?.map(c=><div key={c.hex}><i style={{background:c.hex}}/><b>{c.hex}</b><small>{Math.round(c.share*100)}%</small></div>)}</div><h3 className="subhead">Findings ({result.findings?.length||0})</h3><div className="r3-visual-findings">{result.findings?.map((f,i)=><article key={i}><div><b>{f.title}</b><Pill tone={f.severity==='warning'?'amber':'blue'}>{f.severity}</Pill></div><p>{f.details}</p>{f.similarity!==undefined&&<small>Similarity candidate: {(f.similarity*100).toFixed(1)}%</small>}<small>{f.recommendation}</small></article>)}</div><div className="r3-ocr"><b>Image text extraction</b><p>{result.ocr_message}</p>{result.ocr_text&&<pre>{result.ocr_text}</pre>}</div><p className="r3-disclaimer">{result.disclaimer}</p></section>}
    <section className="panel"><div className="panel-head"><div><h2>Recent visual reviews</h2><p>Saved screening history for this workspace.</p></div></div>{history.length===0?<p className="r3-muted">No visual screening records yet.</p>:<div className="table-wrap"><table><thead><tr><th>ASSET</th><th>FINDINGS</th><th>DATE</th></tr></thead><tbody>{history.slice(0,12).map(item=><tr key={item.id}><td><strong>{item.filename}</strong><small>#{item.id.slice(0,8)}</small></td><td>{item.findings?.length||0}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}</section>
    <div className="r3-footnote"><AlertTriangle size={16}/> Logo matching uses perceptual-hash similarity and can miss resized, recoloured or partially obscured logos. Colour comparison uses RGB distance, not a certified colour-management workflow. OCR is enabled only when Tesseract is installed on the backend host.</div>
  </>;
}

function HorizontalBars({items, empty='No data yet'}) {
  const max = Math.max(1, ...(items||[]).map(x=>x.value));
  if (!items?.length) return <p className="r3-muted">{empty}</p>;
  return <div className="r3-bars">{items.map(item=><div className="r3-bar-row" key={item.label}><span title={item.label}>{item.label}</span><div><i style={{width:`${Math.max(3,(item.value/max)*100)}%`}}/></div><b>{item.value}</b></div>)}</div>;
}
export function GovernanceAnalytics() {
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  async function load(){setBusy(true);try{setData(await api('/api/analytics'));setError('');}catch(e){setError(e.message);}finally{setBusy(false);}}
  useEffect(()=>{load();},[]);
  if(error) return <><div className="page-head"><div><div className="eyebrow">ROUND 3 · GOVERNANCE INTELLIGENCE</div><h1>Governance analytics</h1></div><button className="outline" onClick={load}><RefreshCw size={16}/> Retry</button></div><ErrorNote message={error}/></>;
  if(!data) return <div className="panel r3-loading">Loading governance analytics...</div>;
  const s=data.summary; const maxTimeline=Math.max(1,...data.timeline.map(x=>x.reviews));
  return <>
    <div className="page-head"><div><div className="eyebrow">ROUND 3 · GOVERNANCE INTELLIGENCE</div><h1>Governance analytics</h1><p>Understand recurring brand issues, review outcomes and activity across the workspace.</p></div><button className="outline" onClick={load} disabled={busy}><RefreshCw size={16}/> Refresh</button></div>
    <div className="r3-metrics analytics-metrics"><div className="r3-metric"><small>Total reviews</small><strong>{s.reviews}</strong></div><div className="r3-metric"><small>Findings raised</small><strong>{s.findings}</strong></div><div className="r3-metric"><small>Approval rate</small><strong>{s.approval_rate}%</strong></div><div className="r3-metric"><small>Visual screenings</small><strong>{s.visual_reviews}</strong></div><div className="r3-metric"><small>Open reviews</small><strong>{s.open}</strong></div></div>
    <div className="r3-columns analytics-grid"><section className="panel"><div className="panel-head"><div><h2>Issues by category</h2><p>Finding distribution across all saved text reviews.</p></div></div><HorizontalBars items={data.by_category}/></section><section className="panel"><div className="panel-head"><div><h2>Severity distribution</h2><p>Severity labels assigned by the review engine.</p></div></div><HorizontalBars items={data.by_severity}/></section><section className="panel"><div className="panel-head"><div><h2>Reviews by channel</h2><p>Where submitted content is being reviewed.</p></div></div><HorizontalBars items={data.by_channel}/></section><section className="panel"><div className="panel-head"><div><h2>Review outcomes</h2><p>Human-controlled decision statuses.</p></div></div><HorizontalBars items={data.by_status}/></section></div>
    <div className="r3-columns analytics-bottom"><section className="panel"><div className="panel-head"><div><h2>14-day review activity</h2><p>Text reviews and visual asset screenings by saved date.</p></div></div><div className="r3-timeline">{data.timeline.map(item=><div key={item.date} title={`${item.date}: ${item.reviews} reviews`}><span style={{height:`${Math.max(4,(item.reviews/maxTimeline)*100)}%`}}/><small>{item.date.slice(5)}</small></div>)}</div></section><section className="panel"><div className="panel-head"><div><h2>Recurring issues</h2><p>Repeated quoted issues from saved findings.</p></div></div><HorizontalBars items={data.recurring_issues} empty="No repeated issues have been recorded."/></section></div>
    <div className="r3-footnote"><BarChart3 size={16}/>{data.disclaimer}</div>
  </>;
}
