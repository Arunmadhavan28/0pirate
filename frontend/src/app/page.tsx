"use client";

import React, { useState, useEffect, useCallback, Fragment, useRef } from "react";
import { createClient } from "@supabase/supabase-js";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import {
  User,
  Settings,
  UploadCloud,
  FileText,
  Bot,
  Terminal,
  Clipboard,
  ClipboardCheck,
  LogOut,
  Github,
  Mail,
  KeyRound,
  Trash2,
  X,
  Zap,
  ShieldCheck,
  ArrowUpCircle,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Info,
  Cpu,
  Download
} from "lucide-react";

// --- Syntax + Diff viewer imports ---
import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";
import ReactDiffViewer from "react-diff-viewer-continued";

/* -------------------------------------------------
   Configuration
---------------------------------------------------*/
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

/* Supported provider -> model list */
const MODEL_OPTIONS: Record<string, string[]> = {
  auto: ["(auto-select)"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  anthropic: ["claude-3-haiku-20240307", "claude-3.5-sonnet-20240620"],
  gemini: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro"],
  deepseek: ["deepseek-chat"],
  mistral: ["mistral-large-latest"],
  groq: ["llama-3.1-8b-instant", "llama-3.1-70b-versatile"],
  ollama: ["mistral:latest", "codegemma:latest", "llama3:latest", "qwen2.5-coder:7b-instruct"],
};

/* -------------------------------------------------
   Utilities & Types
---------------------------------------------------*/
type JobStatus = "idle" | "loading" | "result" | "error" | "upgrade";
type ReportFinding = { file?: string; line?: number; message: string; severity?: string; };
type Report = { overall?: any; summary?: any; findings?: ReportFinding[]; status?: string; errors?: number; warnings?: number; };
type ResultShape = { result?: Record<string, string> | string; analysis?: string; validator_report?: Report; sandbox_result?: Report; notice?: string; job_id?: string; [key: string]: any; };
const short = (s: string | undefined, n = 40) => { if (!s) return ""; if (s.length <= n) return s; return s.slice(0, n - 1) + "…"; };

/* -------------------------------------------------
   Polling Hook
---------------------------------------------------*/
function useJobPolling(jobId: string | null, token: string | null, onResult: (data: any) => void, onError: (err: string) => void, setStatus: (s: string) => void) {
    const tokenRef = useRef(token);
    useEffect(() => { tokenRef.current = token; }, [token]);
    useEffect(() => {
        if (!jobId) return;
        let cancelled = false;
        let stepIndex = 0;
        const steps = ["Redacting secrets…", "Abstracting code…", "Building AI prompt…", "Calling LLM…", "Parsing response…", "Validating fix…", "Running sandbox…", "Finalizing…"];
        const poll = async () => {
            if (cancelled) return;
            setStatus(`[ ${steps[stepIndex++ % steps.length]} ]`);
            try {
                const currentToken = tokenRef.current;
                if (!currentToken) throw new Error("Authentication token is missing.");
                const res = await fetch(`${BACKEND_URL}/api/status/${jobId}`, { headers: { Authorization: `Bearer ${currentToken}` } });
                if (!res.ok) { let body; try { body = await res.json(); } catch (_) { body = null; } throw new Error(body?.detail || `Server responded with status ${res.status}`); }
                const data = await res.json();
                if (data.status === "completed") { onResult(data); } else if (data.status === "failed") { throw new Error(data.notice || data.result || "Job failed"); } else { setTimeout(poll, 2200); }
            } catch (e: any) { if (!cancelled) { const msg = e?.message || "An error occurred while polling."; onError(msg); } }
        };
        poll();
        return () => { cancelled = true; };
    }, [jobId, onResult, onError, setStatus]);
}

/* -------------------------------------------------
   Small Components
---------------------------------------------------*/
const Badge = ({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "success" | "warn" | "info" }) => { const cls = tone === "success" ? "px-2 py-1 rounded bg-green-600 text-white text-xs" : tone === "warn" ? "px-2 py-1 rounded bg-amber-500 text-black text-xs" : tone === "info" ? "px-2 py-1 rounded bg-blue-600 text-white text-xs" : "px-2 py-1 rounded bg-gray-200 text-black text-xs"; return <span className={cls}>{children}</span>; };
const ReportCard = ({ title, report }: { title: string; report: Report | undefined | null }) => { if (!report) return null; const summary = report.overall || report.summary || report; const status = summary?.status || (summary?.errors > 0 ? "error" : "ok"); const isSuccess = status === "success" || status === "ok"; const findings = report.findings || []; return (<motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="card p-3 bg-background-light border-border-color mt-4"><details><summary className="font-bold flex items-center gap-2 cursor-pointer">{isSuccess ? <CheckCircle2 className="text-green-500" size={16} /> : <AlertTriangle className="text-amber-400" size={16} />}{title} Report:<span className={`ml-2 capitalize ${isSuccess ? "text-green-600" : "text-amber-500"}`}>{status}</span><span className="text-xs text-text-secondary ml-auto">({summary?.errors || 0} Errors, {summary?.warnings || 0} Warnings)</span></summary><div className="mt-3 pl-3 border-l-2 border-border-secondary text-xs space-y-2 max-h-44 overflow-y-auto">{findings.length > 0 ? (findings.map((f: ReportFinding, i: number) => (<div key={i} className="mb-2"><p className="font-semibold text-sm">{f.file ? `${f.file}${f.line ? `:${f.line}` : ""}` : "General"} - <span className="capitalize">{f.severity || "info"}</span></p><p className="text-text-secondary text-sm">{f.message}</p></div>))) : (<p className="text-text-secondary text-sm">No findings to report.</p>)}</div></details></motion.div>); };
const AuthComponent = () => { const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [isSignUp, setIsSignUp] = useState(false); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false); const handleAuth = async (e?: React.FormEvent) => { if (e) e.preventDefault(); setError(null); setLoading(true); try { if (isSignUp) { const { error } = await supabase.auth.signUp({ email, password }); if (error) setError(error.message); } else { const { error } = await supabase.auth.signInWithPassword({ email, password }); if (error) setError(error.message); } } catch (err: any) { setError(err?.message || "An unexpected error occurred."); } finally { setLoading(false); } }; const oauth = async (provider: "github" | "google") => { setError(null); try { const { error } = await supabase.auth.signInWithOAuth({ provider, options: { redirectTo: window.location.origin } }); if (error) setError(error.message); } catch (e: any) { setError(e.message || "OAuth failed."); } }; return (<motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="card max-w-lg mx-auto p-8"><h2 className="text-2xl font-bold mb-3 text-center">{isSignUp ? "Create an account" : "Sign in"}</h2><form onSubmit={handleAuth} className="flex flex-col gap-3"><input className="input-base" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required /><input className="input-base" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required /><div className="flex gap-2"><button type="submit" disabled={loading} className="btn btn-primary btn-laser flex-1">{isSignUp ? "Sign up" : "Sign in"}</button><button type="button" onClick={() => { setIsSignUp((s) => !s); }} className="btn btn-secondary btn-laser">{isSignUp ? "Have account?" : "Create account"}</button></div></form>{error && <p className="text-accent-destructive mt-3">{error}</p>}<div className="my-4 text-center">— Or continue with —</div><div className="flex gap-3"><button onClick={() => oauth("github")} className="btn btn-secondary flex-1 flex items-center justify-center gap-2"><Github size={16} /> GitHub</button><button onClick={() => oauth("google")} className="btn btn-secondary flex-1 flex items-center justify-center gap-2"><Mail size={16} /> Google</button></div></motion.div>); };
const UpgradePrompt = () => ( <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="p-8 text-center"><h3 className="text-2xl font-bold mb-2">Daily limit reached</h3><p className="text-text-secondary mb-4">Upgrade to Pro for more jobs, priority processing and larger models.</p><div className="grid gap-2 mb-6"><div className="flex items-center gap-2"><ShieldCheck size={16} /> Unlimited "Max Security" jobs</div><div className="flex items-center gap-2"><ArrowUpCircle size={16} /> 10× daily jobs</div><div className="flex items-center gap-2"><Zap size={16} /> Priority processing</div></div><button className="btn btn-primary btn-laser" onClick={() => alert("Redirecting to pricing...")}>Upgrade to Pro</button></motion.div>);

/* -------------------------------------------------
   Account Manager
---------------------------------------------------*/
function AccountManager({ token, email, savedKeys, onKeysChange }: {
  token: string | null;
  email: string | undefined;
  savedKeys: { name: string; provider: string }[];
  onKeysChange: () => void;
}) {
  const [provider, setProvider] = useState("gemini");
  const [apiKey, setApiKey] = useState("");
  const [keyName, setKeyName] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const save = async () => {
    if (!token || !apiKey) {
      setMessage("Please provide a non-empty API key.");
      return;
    }
    const nameToSend = keyName.trim() || provider;
    try {
      const res = await fetch(`${BACKEND_URL}/api/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ provider, name: nameToSend, api_key: apiKey }),
      });
      if (res.ok) {
        setMessage(`Saved key: ${nameToSend}`);
        setApiKey("");
        setKeyName("");
        onKeysChange();
      } else {
        const errData = await res.json();
        setMessage(`Failed to save key: ${errData.detail || "Unknown error"}`);
      }
    } catch (e) {
      console.error("save err", e);
      setMessage("Error saving key");
    }
  };

  const remove = async (nameToDelete: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/keys`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: nameToDelete }),
      });
      if (res.ok) {
        setMessage(`Deleted key: ${nameToDelete}`);
        onKeysChange();
      } else {
        setMessage("Failed to delete key.");
      }
    } catch (e) {
      console.error("delete err", e);
      setMessage("Error deleting key");
    }
  };

  return (
    <div className="p-6 space-y-4">
      <p className="text-sm">Logged in as <span className="font-semibold">{email}</span></p>
      <div className="card p-4 space-y-3">
        <h3 className="flex items-center gap-2"><KeyRound size={16} /> Manage API Keys</h3>
        <input className="input-base" type="text" placeholder="Key name (e.g., 'Personal Gemini Key')" value={keyName} onChange={(e) => setKeyName(e.target.value)} />
        <select className="input-base" value={provider} onChange={(e) => setProvider(e.target.value)}>
          {Object.keys(MODEL_OPTIONS).filter((p) => !["auto", "ollama"].includes(p)).map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input className="input-base" type="password" placeholder="API key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
        <div className="flex gap-2"><button onClick={save} className="btn btn-primary btn-laser flex-1">Save Key</button></div>
        {message && <p className="text-sm">{message}</p>}
        <div className="text-xs text-text-secondary p-2 bg-background-light rounded border border-border-color">
          <strong>Tip:</strong> Give your keys a custom name. If you leave it blank, it will default to the provider's name (e.g., "gemini").
        </div>
      </div>
      <div className="card p-4">
        <h4 className="font-semibold">Saved Keys</h4>
        {savedKeys.length === 0 ? <p className="text-sm text-text-secondary mt-2">No saved keys.</p> : (
          <div className="space-y-1 mt-2">
            {savedKeys.map((key) => (
              <div key={key.name} className="flex justify-between items-center bg-background-light p-2 rounded">
                <span className="truncate font-mono text-sm">{key.name} <span className="text-text-secondary">({key.provider})</span></span>
                <button onClick={() => remove(key.name)} className="btn btn-secondary btn-laser text-accent-destructive p-1"><Trash2 size={16} /></button>
              </div>
            ))}
          </div>
        )}
      </div>
      <button onClick={() => supabase.auth.signOut()} className="btn btn-secondary btn-laser bg-accent-destructive text-white w-full flex items-center justify-center gap-2">
        <LogOut size={16} /> Sign out
      </button>
    </div>
  );
}

/* -------------------------------------------------
   Main Application Component
---------------------------------------------------*/
function MainApp({ token, savedKeys }: { token: string | null; savedKeys: { name: string; provider: string }[] }) {
  type ViewState = JobStatus;
  const [inputMode, setInputMode] = useState<"paste" | "upload">("paste");
  const [pastedCode, setPastedCode] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [errorLog, setErrorLog] = useState("");
  const [task, setTask] = useState("fix_and_secure");
  const [result, setResult] = useState<ResultShape | null>(null);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [status, setStatus] = useState("Select a task, provide code, and run the analysis.");
  const [provider, setProvider] = useState("auto");
  const [model, setModel] = useState("(auto-select)");
  const [jobId, setJobId] = useState<string | null>(null);
  const [tokenSaver, setTokenSaver] = useState(false);
  const [maxSecurity, setMaxSecurity] = useState(true);
  const [chunking, setChunking] = useState(false);
  const [noise, setNoise] = useState(true);
  const [copyOK, setCopyOK] = useState("");
  const [view, setView] = useState<ViewState>("idle");
  const [selectedKeyName, setSelectedKeyName] = useState("");

  const onDrop = useCallback((acceptedFiles: File[]) => { setFiles(prevFiles => [...prevFiles, ...acceptedFiles]); setInputMode("upload"); }, []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });
  const success = useCallback((d: any) => { setResult(d); const r = d.result || {}; if (r && typeof r === "object" && Object.keys(r).length > 0) { setActiveFile(Object.keys(r)[0]); } else { setActiveFile(null); } setView("result"); setStatus("Done"); }, []);
  const fail = useCallback((err: string) => { if (err?.includes?.("Daily job quota") || err?.includes?.("quota")) { setView("upgrade"); } else { setResult({ notice: `Error: ${err}` }); setView("error"); } setStatus("Failed"); }, []);
  useJobPolling(jobId, token, success, fail, setStatus);

  useEffect(() => {
    if (savedKeys) {
      const keysForProvider = savedKeys.filter(k => k.provider === provider);
      if (keysForProvider.length > 0) {
        setSelectedKeyName(keysForProvider[0].name);
      } else {
        setSelectedKeyName("");
      }
    }
  }, [provider, savedKeys]);

  const submit = async () => {
    if (inputMode === "paste" && !pastedCode.trim()) return fail("Please paste your code.");
    if (inputMode === "upload" && files.length === 0) return fail("Please upload files.");
    const requiresKey = provider !== 'auto' && provider !== 'ollama';
    if (requiresKey && !selectedKeyName) { return fail(`Please go to your account panel and save an API key for the '${provider}' provider.`); }
    setView("loading");
    setResult(null);
    setJobId(null);
    setStatus("Submitting…");
    const fd = new FormData();
    if (inputMode === "paste") fd.append("files", new Blob([pastedCode]), "pasted_code.py");
    else files.forEach((f) => fd.append("files", f));
    fd.append("task", task);
    if (errorLog) fd.append("error_log", errorLog);
    fd.append("provider", provider);
    if (model) fd.append("model", model);
    if (selectedKeyName) { fd.append("api_key_name", selectedKeyName); }
    fd.append("token_saver_enabled", String(tokenSaver));
    fd.append("abstraction_enabled", String(maxSecurity));
    fd.append("abstraction_level", maxSecurity ? "paranoid" : "standard");
    fd.append("abstraction_chunking", String(chunking));
    fd.append("abstraction_noise", String(noise));
    try {
      if (!token) throw new Error("Authentication token is missing.");
      const res = await fetch(`${BACKEND_URL}/api/process_code`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd });
      const d = await res.json();
      if (res.ok) { setJobId(d.job_id); setStatus("Job submitted — awaiting result..."); } else { fail(d.detail || d.error || "Submission failed."); }
    } catch (e: any) { fail(e.message || "A network error occurred."); }
  };

  const copy = (textToCopy?: string) => { let text = textToCopy || ""; if (!text && result && result.result) { if (typeof result.result === "string") text = result.result; else if (typeof result.result === "object" && activeFile) text = (result.result as Record<string, string>)[activeFile] || ""; } if (!text) return; navigator.clipboard.writeText(text).then(() => { setCopyOK("Copied!"); setTimeout(() => setCopyOK(""), 2000); }); };
  useEffect(() => { const models = MODEL_OPTIONS[provider] || ["(auto-select)"]; setModel(models[0]); }, [provider]);
  const resultData = result?.result || {};
  const analysisText = result?.analysis || "";
  const activeFileContent = activeFile && typeof resultData === "object" ? (resultData as Record<string, string>)[activeFile] : (typeof resultData === "string" ? resultData : "");

  return (
    <main className="layout-grid fade-in gap-8">
      <section className="flex flex-col gap-6">
        <div className="flex gap-2">{["paste", "upload"].map((m) => (<button key={m} onClick={() => setInputMode(m as any)} className={`btn btn-laser flex-1 ${inputMode === m ? "btn-primary" : "btn-secondary"} transition-transform hover:scale-105`}>{m === "paste" ? "Paste Code" : "Upload Files"}</button>))}</div>
        {inputMode === "paste" ? (<textarea className="code-input min-h-[220px] font-mono text-sm" placeholder="Paste your code here..." value={pastedCode} onChange={(e) => setPastedCode(e.target.value)} />) : (<div {...getRootProps()} className="card text-center p-6 border-2 border-dashed hover:border-accent-primary transition-colors cursor-pointer"><input {...getInputProps()} /><UploadCloud className="w-12 h-12 mx-auto mb-4" /><div className="text-sm">{isDragActive ? "Drop files… " : "Drag & drop files here, or click to select"}</div>{files.length > 0 && (<ul className="mt-4 text-left text-sm space-y-1">{files.map((f) => <li key={f.name} className="truncate">{f.name} ({Math.round(f.size / 1024)} KB)</li>)}</ul>)}</div>)}
        <div className="card p-4 space-y-2"><h4 className="flex items-center gap-2"><Bot size={16} /> Select Task</h4><select className="input-base" value={task} onChange={(e) => setTask(e.target.value)}><option value="fix_and_secure">Fix & Secure</option><option value="code_review">Code Review</option><option value="documentation">Add Documentation</option><option value="refactor">Refactor</option><option value="explain">Explain Code</option></select></div>
        <AnimatePresence>{task === "fix_and_secure" && (<motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="card p-4 space-y-2 overflow-hidden"><h4 className="flex items-center gap-2"><Terminal size={16} /> Terminal Output</h4><textarea className="code-input min-h-[120px] text-sm" placeholder="Paste terminal output (stack traces, error logs) here..." value={errorLog} onChange={(e) => setErrorLog(e.target.value)} /></motion.div>)}</AnimatePresence>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-4 space-y-3"><h4 className="flex items-center gap-2"><Settings size={16} /> Options</h4><label className="flex items-center justify-between cursor-pointer text-sm font-medium"><span>Max Security (Abstraction)</span><input type="checkbox" checked={maxSecurity} onChange={(e) => setMaxSecurity(e.target.checked)} /></label><AnimatePresence>{maxSecurity && (<motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="pl-4 border-l-2 border-border-secondary space-y-3 pt-3 mt-3 overflow-hidden"><label className="flex items-center justify-between cursor-pointer text-sm"><span>Paranoid Noise</span><input type="checkbox" checked={noise} onChange={(e) => setNoise(e.target.checked)} /></label><label className="flex items-center justify-between cursor-pointer text-sm"><span>Chunking (Python only)</span><input type="checkbox" checked={chunking} onChange={(e) => setChunking(e.target.checked)} /></label></motion.div>)}</AnimatePresence><label className="flex items-center justify-between cursor-pointer text-sm font-medium pt-2 border-t border-border-secondary"><span>Token Saver (Diff Output)</span><input type="checkbox" checked={tokenSaver} onChange={(e) => setTokenSaver(e.target.checked)} /></label><div className="text-xs text-text-secondary pt-2">When Token Saver is enabled the UI will show diffs instead of full replaced files to save model tokens and make reviews faster.</div></div>
          <div className="grid gap-2"><select className="input-base" value={provider} onChange={(e) => setProvider(e.target.value)}>{Object.keys(MODEL_OPTIONS).map((p) => <option key={p} value={p}>{p}</option>)}</select><select className="input-base" value={model} onChange={(e) => setModel(e.target.value)} disabled={(MODEL_OPTIONS[provider] || []).length <= 1}>{(MODEL_OPTIONS[provider] || []).map((m) => <option key={m} value={m}>{m}</option>)}</select>
            {provider !== 'auto' && provider !== 'ollama' && (<div className="card p-4 space-y-2"><h4 className="flex items-center gap-2"><KeyRound size={16} /> Select API Key</h4><select className="input-base" value={selectedKeyName} onChange={(e) => setSelectedKeyName(e.target.value)} disabled={savedKeys.filter(k => k.provider === provider).length === 0}>{savedKeys.filter(k => k.provider === provider).length === 0 ? (<option value="">No keys saved for {provider}</option>) : (savedKeys.filter(key => key.provider === provider).map((key) => (<option key={key.name} value={key.name}>{key.name}</option>)))}</select></div>)}
            <div className="card p-3"><div className="flex items-center gap-2 mb-2"><Info size={16} /> Quick Summary</div><div className="text-xs text-text-secondary">Provider: <strong>{provider}</strong><br />Model: <strong>{model}</strong><br />Abstraction: <strong>{maxSecurity ? "Paranoid" : "Standard"}</strong></div></div>
          </div>
        </div>
        <div className="flex gap-3 items-center"><button onClick={submit} disabled={view === "loading"} className={`btn btn-primary btn-laser py-3 text-lg flex-1 ${view === "loading" ? "animate-pulse" : ""}`}>{view === "loading" ? status : "Run Analysis"}</button><button onClick={() => { setPastedCode(""); setFiles([]); setErrorLog(""); setResult(null); setView("idle"); }} className="btn btn-secondary btn-laser">Reset</button></div>
      </section>
      <aside className="card p-4 results-card relative overflow-hidden flex flex-col"><AnimatePresence mode="wait">{view === "loading" && (<motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="processing"><Bot className="mx-auto w-12 h-12 animate-spin mb-4 text-accent-primary" /><p className="typing-dots">{status}</p></motion.div>)}{view === "upgrade" && <UpgradePrompt key="upgrade" />}{(view === "result" || view === "error") && result && (<motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col h-full">{analysisText && (<div className="mb-4 p-3 bg-background-light rounded-lg border border-border-color max-h-48 overflow-y-auto"><h3 className="font-bold mb-2 text-accent-primary flex items-center gap-2"><Bot size={16} /> AI Analysis</h3><pre className="whitespace-pre-wrap text-sm">{analysisText}</pre></div>)}<div className="flex-grow flex flex-col min-h-0"><div className="flex justify-between mb-2 items-center"><div className="text-sm text-text-secondary">{tokenSaver ? "Diff View" : "Full Code"}</div><div className="flex items-center gap-2"><button onClick={() => copy()} className="btn btn-secondary btn-laser flex items-center gap-2">{copyOK ? <ClipboardCheck size={16} /> : <Clipboard size={16} />}{copyOK || "Copy"}</button><Badge tone="info">Job: {short(jobId || "n/a", 12)}</Badge></div></div>{typeof resultData === "object" && Object.keys(resultData as Record<string, string>).length > 0 ? (<div className="flex-grow flex flex-col min-h-0"><div className="flex gap-2 mb-3 flex-wrap border-b border-border-color pb-2">{Object.keys(resultData as Record<string, string>).map((f) => (<button key={f} onClick={() => setActiveFile(f)} className={`btn btn-secondary btn-laser text-xs ${activeFile === f ? "bg-accent-primary text-white" : ""}`}><FileText size={14} /> {short(f, 24)}</button>))}</div><div className="flex-grow overflow-auto text-sm bg-code-editor rounded-md p-2">{tokenSaver ? (<ReactDiffViewer oldValue="" newValue={activeFileContent || ""} splitView={false} useDarkTheme={true} styles={{ diffContainer: { background: "transparent" } }} />) : (<SyntaxHighlighter language="python" style={atomOneDark} customStyle={{ background: "transparent", padding: 0 }} wrapLines={true} wrapLongLines={true}>{activeFileContent || ""}</SyntaxHighlighter>)}</div><div className="mt-3 flex gap-2"><button onClick={() => { if (!activeFile || !activeFileContent) return; const blob = new Blob([activeFileContent], { type: "text/plain" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = activeFile; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); }} className="btn btn-secondary btn-laser flex items-center gap-2"><Download size={16} /> Download File</button><button onClick={() => { if (result?.sandbox_result) { alert("Sandbox result available — see report below."); } else { alert("No sandbox result available for this job."); } }} className="btn btn-secondary btn-laser flex items-center gap-2"><Cpu size={16} /> Check Sandbox</button></div></div>) : (<pre className="whitespace-pre-wrap flex-grow overflow-auto text-sm">{result.notice || "No code returned. Check analysis for details."}</pre>)}</div><div className="mt-3"><ReportCard title="Validation" report={(result as ResultShape).validator_report} /><ReportCard title="Sandbox" report={(result as ResultShape).sandbox_result} /></div></motion.div>)}{view === "idle" && (<motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="processing"><p>{status}</p></motion.div>)}</AnimatePresence></aside>
    </main>
  );
}

/* -------------------------------------------------
   Top-level Home wrapper
---------------------------------------------------*/
export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [savedKeys, setSavedKeys] = useState<{ name: string; provider: string }[]>([]);

  // 1. Add new state to hold the user's subscription tier.
  const [userTier, setUserTier] = useState<string | null>(null);

  const loadKeys = useCallback(async () => {
    if (!token) {
      setSavedKeys([]);
      return;
    }
    try {
      const res = await fetch(`${BACKEND_URL}/api/keys`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error("Could not fetch keys");

      const data = await res.json();
      setSavedKeys(data.keys || []);
    } catch (e) {
      console.error("Failed to load keys:", e);
      setSavedKeys([]);
    }
  }, [token]);

  // 2. Add a function to load the user's profile and tier from Supabase.
  const loadUserProfile = useCallback(async (userId: string) => {
    if (!userId) return;
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('tier')
        .eq('id', userId)
        .single();

      if (error) {
        console.error("Could not find or fetch user profile:", error.message);
        setUserTier("free"); // Default to 'free' as per your backend logic
        return;
      }

      if (data) {
        setUserTier(data.tier || "free");
      }
    } catch (e) {
      console.error("Failed to load user profile:", e);
      setUserTier("free"); // Default on any other error
    }
  }, []);

  useEffect(() => {
    if (token) {
      loadKeys();
    }
  }, [token, loadKeys]);

  useEffect(() => {
    const handleAuthChange = async (session: any) => {
        setUser(session?.user ?? null);
        setToken(session?.access_token ?? null);

        // 3. When the user session loads or changes, fetch their tier.
        if (session?.user) {
          await loadUserProfile(session.user.id);
        } else {
          setUserTier(null); // Clear the tier when the user logs out.
        }
    };

    // Handle the initial session load
    supabase.auth.getSession().then(({ data: { session } }) => {
        handleAuthChange(session);
    });

    // Listen for future auth changes (sign in, sign out)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
        handleAuthChange(session);
    });

    return () => {
      subscription?.unsubscribe();
    };
  }, [loadUserProfile]);

  // Helper function to determine badge style based on tier
  const getTierBadgeProps = (tier: string | null) => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      case 'pro':
        return { tone: 'info', children: 'Pro' };
      case 'enterprise':
        return { tone: 'success', children: 'Enterprise' };
      default:
        return { tone: 'default', children: 'Free' };
    }
  };

  return (
    <div className="app min-h-screen p-6">
      <header className="app-header flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="app-title text-xl font-bold flex items-center gap-2">
              <span className="inline-block w-8 h-8 rounded bg-accent-primary flex items-center justify-center text-white">0</span>
              Pirate
            </h1>
            <div className="text-sm text-text-secondary">Secure & Refactor Your Code with AI</div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-2">
              <button onClick={() => setPanelOpen(true)} className="btn btn-secondary btn-laser rounded-full p-2">
                <User size={16} />
              </button>
            </div>
          ) : null}
        </div>
      </header>

      {!user ? (
        <AuthComponent />
      ) : (
        <Fragment>
          <AnimatePresence>
            {panelOpen && (
              <motion.div key="panel" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 300, damping: 30 }} className="fixed top-0 right-0 h-full w-full max-w-lg bg-background-dark shadow-2xl z-50 overflow-y-auto">
                <div className="flex justify-between items-center p-4 border-b border-border-color">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold">Account</h3>

                    {/* 4. Dynamically render the badge based on the fetched tier */}
                    {userTier && (
                      <Badge {...getTierBadgeProps(userTier)} />
                    )}

                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => setPanelOpen(false)} className="btn btn-secondary btn-laser p-2"><X size={16} /></button>
                  </div>
                </div>

                <AccountManager
                  token={token}
                  email={user?.email}
                  savedKeys={savedKeys}
                  onKeysChange={loadKeys}
                />
              </motion.div>
            )}
          </AnimatePresence>

          <MainApp token={token} savedKeys={savedKeys} />
        </Fragment>
      )}
    </div>
  );
}