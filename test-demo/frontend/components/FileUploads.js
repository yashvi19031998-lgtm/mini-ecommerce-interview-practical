'use client';

// File Uploads: contacts from Excel, vCard, Word, e-mail (.eml / .mbox), PDF, text / web pages and visiting-card
// photos (OCR, when Tesseract is installed). Excel sheets open the Contact Import mapping; every other file shows
// checked contacts. Both reuse BulkContacts (preset) for duplicates, export and Save to Leads.
// Backend: file_uploads.py via /api/file-uploads/*.

import React, { useEffect, useRef, useState } from 'react';
import { FolderUp, Upload, Loader2, AlertTriangle, ShieldCheck, FileSpreadsheet, Contact2, FileText, Mail, FileType2, Image as ImageIcon } from 'lucide-react';
import { fetchFileUploadOptions, parseUploadedFile } from '../lib/api';
import BulkContacts from './BulkContacts';

const GROUPS = [
  { icon: FileSpreadsheet, label: 'Excel', exts: ['.xlsx'], note: 'Sheets open the column-matching screen' },
  { icon: Contact2, label: 'vCard', exts: ['.vcf'], note: 'Phone / Outlook contact export' },
  { icon: FileText, label: 'Word / Text', exts: ['.docx', '.txt', '.html', '.htm'], note: 'Contact blocks are found in the text' },
  { icon: Mail, label: 'E-mails', exts: ['.eml', '.mbox'], note: 'Sender + signature (no-reply skipped)' },
  { icon: FileType2, label: 'PDF', exts: ['.pdf'], note: 'Brochures, expo catalogues (text PDFs)' },
  { icon: ImageIcon, label: 'Card photo', exts: ['.jpg', '.jpeg', '.png', '.webp'], note: 'Visiting cards — OCR' }
];

export default function FileUploads({ onLeadsSaved }) {
  const [opts, setOpts] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [parsed, setParsed] = useState(null);
  const [sheet, setSheet] = useState(0);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { fetchFileUploadOptions().then(setOpts).catch(err => setError(err.message || 'Could not load. Is the Python backend running?')); }, []);

  const ocr = opts?.ocr;
  const accept = Object.keys(opts?.types || {}).join(',');

  const handle = (f) => {
    if (!f) return;
    setError(''); setParsed(null); setSheet(0);
    const ext = (f.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
    if (opts && !opts.types[ext]) { setError(`Unsupported file type '${ext || '?'}'. Supported: ${Object.keys(opts.types).join(', ')}`); return; }
    if (ext === '.xls' || ext === '.doc') { setError('Old Office format — open it and save as .xlsx / .docx'); return; }
    if (f.size > (opts?.maxFileBytes || 10485760)) { setError('The file is larger than 10 MB — split it into smaller files'); return; }
    if (['.jpg', '.jpeg', '.png', '.webp'].includes(ext) && ocr && !ocr.available) { setError(ocr.reason); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      setBusy(true);
      try {
        const res = await parseUploadedFile(f.name, String(reader.result || ''));
        setParsed(res);
      } catch (err) {
        setError(err.message || 'The file could not be read');
      } finally {
        setBusy(false);
      }
    };
    reader.onerror = () => setError('The file could not be read');
    reader.readAsDataURL(f);
  };

  const preset = parsed && (parsed.mode === 'table'
    ? { kind: 'csv', name: `${parsed.file.replace(/\.[^.]+$/, '')}${parsed.sheets.length > 1 ? ` - ${parsed.sheets[sheet].name}` : ''}.csv`, text: parsed.sheets[sheet].csv }
    : { kind: 'result', name: parsed.file, results: parsed.results, counts: parsed.counts });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><FolderUp size={18} /> File Uploads</div>
            <div className="theme-panel-sub">Upload a file you already have — Excel list, phone contacts, expo catalogue, brochure, e-mails or a visiting card — and turn the contacts in it into leads.</div>
          </div>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}>
          <ShieldCheck size={14} />
          <span>The file is read on your server and not kept. Up to 10 MB. Duplicates (inside the file and against your Leads) are shown before anything is saved; nothing is sent to anyone.</span>
        </div>

        <div className="jp-status-row" style={{ marginBottom: '0.75rem', flexWrap: 'wrap' }}>
          {GROUPS.map(g => {
            const off = g.label === 'Card photo' && ocr && !ocr.available;
            return (
              <span key={g.label} className={`jp-status-chip ${off ? 'empty' : 'ok'}`} title={off ? ocr.reason : g.note}>
                {React.createElement(g.icon, { size: 12, style: { verticalAlign: '-2px', marginRight: 4 } })}
                {g.label} <span style={{ opacity: 0.7 }}>{g.exts.join(' ')}</span>{off ? ' — needs Tesseract' : ''}
              </span>
            );
          })}
        </div>

        <div role="button" tabIndex={0} aria-label="Choose or drop a file"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click(); } }}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files?.[0]); }}
          style={{ border: `2px dashed ${drag ? 'var(--accent, #2563eb)' : 'var(--border-light, #d6d9de)'}`, borderRadius: 12, padding: '28px 16px',
            textAlign: 'center', cursor: busy ? 'progress' : 'pointer', background: drag ? 'rgba(37,99,235,0.05)' : 'transparent' }}>
          {busy ? <Loader2 size={22} className="animate-spin" /> : <Upload size={22} />}
          <div style={{ marginTop: 8, fontWeight: 600 }}>{busy ? 'Reading the file…' : parsed ? `Loaded ${parsed.file} — choose another file` : 'Drop a file here or click to choose'}</div>
          <div className="jp-hint">{accept || '.xlsx .vcf .docx .eml .mbox .pdf .txt .html .jpg .png'}</div>
          <input ref={inputRef} type="file" accept={accept} style={{ display: 'none' }} aria-label="Choose file"
            onChange={(e) => { handle(e.target.files?.[0]); e.target.value = ''; }} />
        </div>
        {error && <div role="alert" className="jp-alert jp-alert-error" style={{ marginTop: '0.75rem' }}><AlertTriangle size={14} /> {error}</div>}
        {parsed?.mode === 'table' && parsed.sheets.length > 1 && (
          <div className="form-group" style={{ marginTop: '0.75rem', maxWidth: 360 }}>
            <label className="form-label" htmlFor="fu-sheet">Sheet</label>
            <select id="fu-sheet" className="theme-form-input" value={sheet} onChange={(e) => setSheet(Number(e.target.value))}>
              {parsed.sheets.map((s, i) => <option key={s.name + i} value={i}>{s.name} ({s.rows} rows)</option>)}
            </select>
          </div>
        )}
        {parsed && <div className="jp-hint" style={{ marginTop: 8 }}>{parsed.type} file · {parsed.mode === 'table' ? 'match the columns below, then Check contacts' : `${parsed.results.length} contact${parsed.results.length === 1 ? '' : 's'} found`}</div>}
      </div>

      {preset && <BulkContacts key={`${parsed.file}-${sheet}`} tool="import" preset={preset} onLeadsSaved={onLeadsSaved} />}
    </div>
  );
}
