"use client";

import {
  useState,
  useEffect,
  useCallback,
  Fragment,
} from "react";
import { createClient } from "@supabase/supabase-js";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, Settings, UploadCloud, FileText, Bot,
  Clipboard, ClipboardCheck, LogOut, Github, Mail,
  KeyRound, Trash2, X, Zap, ShieldCheck, ArrowUpCircle
} from "lucide-react";

/* -------------------------------------------------
   Configuration
---------------------------------------------------*/
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

const MODEL_OPTIONS: Record<string, string[]> = {
  auto: ["(auto-select)"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  anthropic: ["claude-3-haiku-20240307", "claude-3.5-sonnet-20240620"],
  gemini: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro"],
  deepseek: ["deepseek-chat"],
  mistral: ["mistral-large-latest"],
  groq: ["llama-3.1-8b-instant", "llama-3.1-70b-versatile"],
  ollama: ["mistral:latest", "codegemma:latest", "llama3:latest","qwen2.5-coder:7b-instruct"],
};

/* -------------------------------------------------
   Polling hook
---------------------------------------------------*/
function useJobPolling(
  jobId: string | null,
  token: string | null,
  onResult: (data: any) => void,
  onError: (err: string) => void,
  setStatus: (s: string) => void
) {
  useEffect(() => {
    if (!jobId || !token) return;
    let cancelled = false;
    const steps = [
      "Redacting secrets…",
      "Validating code…",
      "Building AI prompt…",
      "Calling LLM…",
      "Parsing response…",
      "Restoring secrets…",
      "Finalizing…",
    ];
    let i = 0;
    const poll = async () => {
      if (!cancelled) setStatus(`[ ${steps[i % steps.length]} ]`);
      i++;
      try {
        const r = await fetch(`${BACKEND_URL}/api/status/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(`Status ${r.status}`);
        const d = await r.json();
        if (d.status === "completed") onResult(d);
        else if (d.status === "failed")
          throw new Error(d.result || "Job failed");
        else setTimeout(poll, 2500);
      } catch (e: any) {
        if (!cancelled) onError(e.message || "Polling error");
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId, token, onResult, onError, setStatus]);
}

/* -------------------------------------------------
   Auth
---------------------------------------------------*/
function AuthComponent() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    let res;
    if (isSignUp) {
      res = await supabase.auth.signUp({ email, password });
    } else {
      res = await supabase.auth.signInWithPassword({ email, password });
    }
    if (res.error) setError(res.error.message);
  };

  const oauth = async (provider: "github" | "google") => {
    const { error } = await supabase.auth.signInWithOAuth({ provider });
    if (error) setError(error.message);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="card max-w-md p-8 mx-auto shadow-xl"
    >
      <h2 className="text-center text-2xl font-bold mb-4">
        {isSignUp ? "Create an Account" : "Welcome to 0Pirate"}
      </h2>
      <form
        onSubmit={handleAuth}
        className="flex flex-col gap-3"
      >
        <input
          className="input-base"
          type="email"
          placeholder="Email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="input-base"
          type="password"
          placeholder="Password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" className="btn btn-primary btn-laser">
          {isSignUp ? "Sign Up" : "Log In"}
        </button>
      </form>
      {error && <p className="text-accent-destructive mt-3 text-center">{error}</p>}
      <p
        className="mt-4 text-center cursor-pointer hover:underline"
        onClick={() => setIsSignUp((v) => !v)}
      >
        {isSignUp
          ? "Already have an account? Log in"
          : "Don't have an account? Sign up"}
      </p>
      <div className="my-6 text-center">— Or —</div>
      <button onClick={() => oauth("github")} className="btn btn-secondary btn-laser mb-2 flex items-center justify-center gap-2">
        <Github /> Continue with GitHub
      </button>
      <button
        onClick={() => oauth("google")}
        className="btn btn-secondary btn-laser bg-white text-black hover:bg-gray-200 flex items-center justify-center gap-2"
      >
        <Mail /> Continue with Google
      </button>
    </motion.div>
  );
}

/* -------------------------------------------------
   Upgrade Prompt
---------------------------------------------------*/
const UpgradePrompt = () => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    className="flex flex-col items-center justify-center text-center p-8"
  >
    <h3 className="text-2xl font-bold mb-2">Daily Limit Reached</h3>
    <p className="mb-4 text-text-secondary">
      Upgrade to unlock more jobs and premium features.
    </p>
    <ul className="text-left mb-6 space-y-2">
      <li className="flex items-center gap-2"><ShieldCheck className="text-green-400"/> Unlimited Max Security jobs</li>
      <li className="flex items-center gap-2"><ArrowUpCircle className="text-blue-400"/> 10x more daily jobs</li>
      <li className="flex items-center gap-2"><Zap className="text-pink-400"/> Priority processing</li>
    </ul>
    <button
      className="btn btn-primary btn-laser flex items-center gap-2"
      onClick={() => alert("Redirecting to pricing page…")}
    >
       Upgrade to Pro
    </button>
  </motion.div>
);

/* -------------------------------------------------
   Account Manager
---------------------------------------------------*/
function AccountManager({ token, email }: { token: string | null; email: string | undefined }) {
  const [provider, setProvider] = useState("gemini");
  const [apiKey, setApiKey] = useState("");
  const [keys, setKeys] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const loadKeys = useCallback(async () => {
    if (!token) return;
    const r = await fetch(`${BACKEND_URL}/api/keys`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.ok) {
      const d = await r.json();
      setKeys(d.providers || []);
    }
  }, [token]);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  const save = async () => {
    if (!token || !apiKey) return;
    const r = await fetch(`${BACKEND_URL}/api/keys`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    setMsg(r.ok ? `Saved key for ${provider}` : "Error saving key");
    setApiKey("");
    loadKeys();
  };

  const del = async (p: string) => {
    if (!token) return;
    await fetch(`${BACKEND_URL}/api/keys`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ provider: p }),
    });
    loadKeys();
  };

  return (
    <div className="p-6 space-y-4">
      <p className="text-sm">Logged in as <span className="font-semibold">{email}</span></p>
      <div className="card p-4 space-y-3">
        <h3 className="flex items-center gap-2"><KeyRound /> Manage API Keys</h3>
        <select className="input-base" value={provider} onChange={(e) => setProvider(e.target.value)}>
          {Object.keys(MODEL_OPTIONS)
            .filter((p) => !["auto", "ollama"].includes(p))
            .map((p) => <option key={p}>{p}</option>)}
        </select>
        <input
          className="input-base"
          type="password"
          placeholder="Enter API key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <button onClick={save} className="btn btn-primary btn-laser">Save Key</button>
        {msg && <p>{msg}</p>}
      </div>

      <div className="card p-4">
        <h4>Saved Keys</h4>
        {keys.length === 0 && <p>No keys saved.</p>}
        {keys.map((k) => (
          <div key={k} className="flex justify-between items-center mt-2">
            {k}
            <button
              onClick={() => del(k)}
              className="btn btn-secondary btn-laser text-accent-destructive flex items-center gap-1"
            >
              <Trash2 size={16}/> Delete
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={() => supabase.auth.signOut()}
        className="btn btn-secondary btn-laser bg-accent-destructive text-white mt-4 flex items-center gap-2"
      >
        <LogOut /> Log out
      </button>
    </div>
  );
}

/* -------------------------------------------------
   Main App
---------------------------------------------------*/
function MainApp({ token }: { token: string | null }) {
  type ViewState = 'idle' | 'loading' | 'result' | 'error' | 'upgrade';
  const [inputMode, setInputMode] = useState<"paste" | "upload">("paste");
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<any>(null);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [status, setStatus] = useState("Idle");
  const [task, setTask] = useState("fix_and_secure");
  const [provider, setProvider] = useState("auto");
  const [model, setModel] = useState("(auto-select)");
  const [jobId, setJobId] = useState<string | null>(null);
  const [tokenSaver, setTokenSaver] = useState(false);
  const [maxSecurity, setMaxSecurity] = useState(true);
  const [copyOK, setCopyOK] = useState("");
  const [view, setView] = useState<ViewState>("idle");

  const onDrop = useCallback((f: File[]) => setFiles(f), []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  const success = useCallback((d: any) => {
    setResult(d.result);
    if (d.result && typeof d.result === "object") {
      setActiveFile(Object.keys(d.result)[0]);
    }
    setView("result");
    setStatus("Done");
  }, []);

  const fail = useCallback((err: string) => {
    if (err.includes("Daily job quota exceeded")) {
      setView("upgrade");
    } else {
      setResult(`Error: ${err}`);
      setView("error");
    }
    setStatus("Failed");
  }, []);

  useJobPolling(jobId, token, success, fail, setStatus);

  const submit = async () => {
    if (inputMode === "paste" && !pasted.trim()) return fail("Paste code first");
    if (inputMode === "upload" && files.length === 0) return fail("Upload files first");
    setView("loading");
    setResult(null);
    setStatus("Submitting…");
    const fd = new FormData();
    if (inputMode === "paste")
      fd.append("files", new Blob([pasted]), "pasted_code.py");
    else files.forEach((f) => fd.append("files", f));
    fd.append("task", task);
    fd.append("provider", provider);
    fd.append("token_saver_enabled", String(tokenSaver));
    fd.append("abstraction_enabled", String(maxSecurity));
    if (model) fd.append("model", model);
    try {
      if (!token) throw new Error("No auth token");
      const r = await fetch(`${BACKEND_URL}/api/process_code`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const d = await r.json();
      if (r.ok) setJobId(d.job_id);
      else fail(d.detail || "Submission failed");
    } catch (e: any) { fail(e.message || "Network error"); }
  };

  const copy = () => {
    let txt = "";
    if (result) {
      if (typeof result === "object" && activeFile) txt = result[activeFile];
      else if (typeof result === "string") txt = result;
    }
    if (txt) {
      navigator.clipboard.writeText(txt).then(() => {
        setCopyOK("Copied!");
        setTimeout(() => setCopyOK(""), 2000);
      });
    }
  };

  useEffect(() => {
    const models = MODEL_OPTIONS[provider] || ["(auto-select)"];
    setModel(models[0]);
  }, [provider]);

  return (
    <main className="layout-grid fade-in gap-8">
      <section className="flex flex-col gap-6">
        <div className="flex gap-2">
          {["paste","upload"].map(m => (
            <button
              key={m}
              onClick={() => setInputMode(m as any)}
              className={`btn btn-laser flex-1 ${inputMode === m ? 'btn-primary' : 'btn-secondary'} transition-transform hover:scale-105`}
            >
              {m === "paste" ? "Paste Code" : "Upload Files"}
            </button>
          ))}
        </div>

        {inputMode === "paste" ? (
          <textarea
            className="code-input min-h-[280px]"
            placeholder="Paste your code here..."
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
          />
        ) : (
          <div
            {...getRootProps()}
            className="card text-center p-6 border-2 border-dashed hover:border-accent-primary transition-colors cursor-pointer"
          >
            <input {...getInputProps()} />
            <UploadCloud className="w-12 h-12 mx-auto mb-4" />
            {isDragActive ? "Drop files…" : "Drag & drop files or click"}
            {files.length > 0 && (
              <ul className="mt-4 text-left">
                {files.map((f) => <li key={f.name}>{f.name}</li>)}
              </ul>
            )}
          </div>
        )}

        <div className="card p-4 space-y-2">
          <h4 className="flex items-center gap-2"><Settings /> Configuration</h4>
          <label><input type="checkbox" checked={maxSecurity} onChange={(e) => setMaxSecurity(e.target.checked)} /> Max Security</label>
          <label><input type="checkbox" checked={tokenSaver} onChange={(e) => setTokenSaver(e.target.checked)} /> Token Saver</label>
        </div>

        <div className="grid gap-2">
          <select className="input-base" value={task} onChange={(e) => setTask(e.target.value)}>
            <option value="fix_and_secure">Fix & Secure</option>
            <option value="code_review">Code Review</option>
            <option value="documentation">Add Documentation</option>
            <option value="refactor">Refactor</option>
          </select>

          <select className="input-base" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {Object.keys(MODEL_OPTIONS).map((p) => <option key={p}>{p}</option>)}
          </select>

          <select className="input-base" value={model} onChange={(e) => setModel(e.target.value)} disabled={MODEL_OPTIONS[provider].length <= 1}>
            {MODEL_OPTIONS[provider].map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>

        <button
          onClick={submit}
          disabled={view === "loading"}
          className={`btn btn-primary btn-laser py-3 text-lg hover:scale-105 transition-transform ${
            view === "loading" ? "animate-pulse" : ""
          }`}
        >
          {view === "loading" ? status : "Run Analysis"}
        </button>
      </section>

      <aside className="card p-4 results-card relative overflow-hidden">
        <AnimatePresence mode="wait">
          {view === "loading" && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="processing"
            >
              <Bot className="mx-auto w-12 h-12 animate-spin mb-4 text-accent-primary" />
              <p className="typing-dots">{status}</p>
            </motion.div>
          )}
          {view === "upgrade" && <UpgradePrompt key="upgrade"/>}
          {(view === "result" || view === "error") && result && (
            <motion.div
              key="result"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="flex justify-between mb-2">
                <div className="text-sm text-text-secondary">
                  {tokenSaver ? 'Diff view (Token Saver)' : 'Full code'}
                </div>
                <button onClick={copy} className="btn btn-secondary btn-laser flex items-center gap-1">
                  {copyOK ? <ClipboardCheck size={16}/> : <Clipboard size={16}/>}{copyOK || "Copy"}
                </button>
              </div>
              {typeof result === "object" ? (
                <div>
                  <div className="flex gap-2 mb-3 flex-wrap">
                    {Object.keys(result).map((f) => (
                      <button
                        key={f}
                        onClick={() => setActiveFile(f)}
                        className={`btn btn-secondary btn-laser ${activeFile === f ? 'bg-accent-primary text-white' : ''}`}
                      >
                        <FileText size={14}/> {f}
                      </button>
                    ))}
                  </div>
                  <pre className="whitespace-pre-wrap">{activeFile ? result[activeFile] : ""}</pre>
                </div>
              ) : (
                <pre className="whitespace-pre-wrap">{result}</pre>
              )}
            </motion.div>
          )}
          {view === "idle" && (
            <motion.p key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {status}
            </motion.p>
          )}
        </AnimatePresence>
      </aside>
    </main>
  );
}

/* -------------------------------------------------
   Home wrapper
---------------------------------------------------*/
export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [panel, setPanel] = useState(false);

  useEffect(() => {
    const init = async () => {
      const { data } = await supabase.auth.getSession();
      setUser(data.session?.user ?? null);
      setToken(data.session?.access_token ?? null);
    };
    init();
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => {
      setUser(s?.user ?? null);
      setToken(s?.access_token ?? null);
    });
    return () => { sub.subscription.unsubscribe(); };
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1 className="app-title flex items-center gap-2">0Pirate</h1>
          <p className="app-tagline">Secure & Refactor Your Code with AI</p>
        </div>
        {user && (
          <button
            onClick={() => setPanel(true)}
            className="btn btn-secondary btn-laser rounded-full p-2 hover:scale-110 transition-transform"
          >
            <User />
          </button>
        )}
      </header>

      {!user ? (
        <AuthComponent />
      ) : (
        <Fragment>
          <AnimatePresence>
            {panel && (
              <motion.div
                key="panel"
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className="fixed top-0 right-0 h-full w-full max-w-sm bg-background-dark shadow-2xl z-50 overflow-y-auto"
              >
                <div className="flex justify-end p-4">
                  <button
                    onClick={() => setPanel(false)}
                    className="btn btn-secondary btn-laser p-2 hover:scale-110 transition-transform"
                  >
                    <X />
                  </button>
                </div>
                <AccountManager token={token} email={user.email} />
              </motion.div>
            )}
          </AnimatePresence>
          <MainApp token={token} />
        </Fragment>
      )}
    </div>
  );
}
