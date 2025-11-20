"use client";

import React, { useState, useEffect, useCallback, Fragment, useRef } from "react";
import { createClient } from "@supabase/supabase-js";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion";

import {
  User, Bot, Terminal, Clipboard, ClipboardCheck, LogOut, Github, Mail, KeyRound,
  Trash2, X, ShieldCheck, FileText, Zap, HelpCircle, Code, Settings, Edit, ChevronLeft, Loader2, MessageSquare, ExternalLink,
  UploadCloud, ClipboardPaste, Crown,FlaskConical,Box,AlertCircle
} from "lucide-react";

import ReactMarkdown from 'react-markdown';
import LandingPage from "./landing_page";
import PricingPage from "./pricing";
import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";

import Script from "next/script";


/* --- Interactive Components --- */
function InteractiveBackground() {
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      document.body.style.setProperty('--mouse-x', `${e.clientX}px`);
      document.body.style.setProperty('--mouse-y', `${e.clientY}px`);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);
  return null;
}

function InteractiveBotIcon() {
  const ref = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springConfig = { damping: 20, stiffness: 200, mass: 0.5 };
  const springX = useSpring(mouseX, springConfig);
  const springY = useSpring(mouseY, springConfig);
  const rotateX = useTransform(springY, [-0.5, 0.5], ["15deg", "-15deg"]);
  const rotateY = useTransform(springX, [-0.5, 0.5], ["-15deg", "15deg"]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const { width, height, left, top } = rect;
      const mouseX_relative = e.clientX - left;
      const mouseY_relative = e.clientY - top;
      mouseX.set((mouseX_relative / width) - 0.5);
      mouseY.set((mouseY_relative / height) - 0.5);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  return (
    <motion.div ref={ref} style={{ transformStyle: "preserve-3d", rotateX, rotateY }} className="mb-6 lp-hero-icon">
      <div style={{ transform: "translateZ(20px)" }}><Bot size={40} /></div>
    </motion.div>
  );
}

// --- Animation Variants ---
const fadeInUp = { initial: { opacity: 0, y: 50 }, animate: { opacity: 1, y: 0, transition: { duration: 0.8, ease: "easeOut" } } };
const staggerContainer = { animate: { transition: { staggerChildren: 0.1 } } };
const scaleIn = { initial: { opacity: 0, scale: 0.95 }, animate: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.95 } };

/* -------------------------------------------------
   Configuration
---------------------------------------------------*/
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "https://api.0pirate.com";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

const MODEL_OPTIONS: Record<string, string[]> = {
  auto: ["(auto-select)"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  anthropic: ["claude-3-haiku-20240307", "claude-3-5-sonnet-20240620"],
  gemini: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro", "gemini-2.5-flash", "gemini-2.5-pro"],
  deepseek: ["deepseek-chat"],
  mistral: ["mistral-large-latest"],
  groq: ["llama-3.1-8b-instant", "llama-3.1-70b-versatile"],
  ollama: ["mistral:latest", "codegemma:latest", "llama3:latest", "qwen2.5-coder:7b-instruct"],
};

/* -------------------------------------------------
   Types and Hooks
---------------------------------------------------*/
type JobStatus = "idle" | "loading" | "result" | "error" | "upgrade";
type ResultShape = { result?: Record<string, string> | string; analysis?: string; notice?: string; job_id?: string;sandbox_result?: Record<string, any> | null; // Added sandbox_result
  validation_result?: Record<string, any> | null; };

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
            setStatus(`${steps[stepIndex++ % steps.length]}`);
            try {
                const headers: HeadersInit = {};
                if (tokenRef.current) {
                    headers['Authorization'] = `Bearer ${tokenRef.current}`;
                }
                const res = await fetch(`${BACKEND_URL}/api/status/${jobId}`, { headers });
                if (!res.ok) { let body; try { body = await res.json(); } catch (_) { body = null; } throw new Error(body?.detail || `Server responded with status ${res.status}`); }
                const data = await res.json();
                if (data.status === "completed") { onResult(data); } else if (data.status === "failed") { throw new Error(data.notice || data.result || "Job failed"); } else { setTimeout(poll, 2200); }
            } catch (e: any) { if (!cancelled) { const msg = e?.message || "An error occurred while polling."; onError(msg); } }
        };
        poll();
        return () => { cancelled = true; };
    }, [jobId, onResult, onError, setStatus]);
}

function useCursorGlow(ref: React.RefObject<HTMLElement>) {
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      ref.current.style.setProperty('--mouse-x', `${x}px`);
      ref.current.style.setProperty('--mouse-y', `${y}px`);
    }
  }, [ref]);

  return { onMouseMove: handleMouseMove };
}

/* -------------------------------------------------
   Small Reusable Components
---------------------------------------------------*/
const Badge = ({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) => {
    let cls = "";
    switch(tone) {
        case "success":
            cls = "inline-flex items-center px-3 py-1 rounded-full bg-emerald-600/20 border border-emerald-600/30 text-emerald-300 text-xs font-medium";
            break;
        case "info":
            cls = "inline-flex items-center px-3 py-1 rounded-full bg-blue-600/20 border border-blue-600/30 text-blue-300 text-xs font-medium";
            break;
        case "free":
            // --- UPGRADED "FREE" BADGE STYLE WITH REFINED SHAPE ---
            cls = "inline-flex items-center px-3 py-1 rounded-lg bg-gray-800 border border-gray-600/80 text-gray-300 text-xs font-medium shadow-inner shadow-black/20";
            break;
        default:
            cls = "inline-flex items-center px-3 py-1 rounded-full bg-gray-500/20 border border-gray-500/30 text-gray-300 text-xs font-medium";
    }
    return <span className={cls}>{children}</span>; 
};

const LoadingSpinner = ({ size = 20, className = "" }: { size?: number; className?: string }) => (
  <motion.div className={`inline-block ${className}`} animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }}>
    <Loader2 size={size} />
  </motion.div>
);

/* -------------------------------------------------
   Modal and View Components
---------------------------------------------------*/
const AuthComponent = ({ onAuthSuccess }: { onAuthSuccess: () => void; }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const authMethod = isSignUp ? supabase.auth.signUp : supabase.auth.signInWithPassword;
      const { error, data } = await authMethod({ email, password });
      if (error) {
        setError(error.message);
      } else if (data.user || data.session) {
        onAuthSuccess();
      } else {
         setError("Please check your email to verify your account.");
      }
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const oauth = async (provider: "github" | "google") => {
    setError(null);
    const { error } = await supabase.auth.signInWithOAuth({ 
      provider, 
      options: { redirectTo: window.location.origin } 
    });
    if (error) setError(error.message);
  };

  return (
    <div className="auth-container">
      <motion.div 
        className="auth-header"
        variants={fadeInUp}
        initial="initial"
        animate="animate"
      >
        <div className="flex justify-center mb-6">
          <InteractiveBotIcon />
        </div>
        <h1 className="flex items-center justify-center gap-3 text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          0Pirate
        </h1>
        <p className="text-text-secondary mt-3 text-lg">
          {isSignUp ? "Create a free account to continue" : "Welcome back! Sign in"}
        </p>
      </motion.div>
      
      <motion.div 
        className="card auth-card"
        variants={scaleIn}
        initial="initial"
        animate="animate"
      >
        <div className="auth-social-buttons flex flex-col gap-3">
          <motion.button 
            onClick={() => oauth("github")} 
            className="btn btn-secondary auth-social-button"
            variants={fadeInUp}
          >
            <Github size={18} /> 
            Continue with GitHub
          </motion.button>
          <motion.button 
            onClick={() => oauth("google")} 
            className="btn btn-secondary auth-social-button"
            variants={fadeInUp}
          >
            <Mail size={18} /> 
            Continue with Google
          </motion.button>
        </div>
        
        <div className="auth-divider">or continue with email</div>
        
        <form onSubmit={handleAuth} className="flex flex-col gap-4">
          <motion.input 
            className="input-base" 
            type="email" 
            placeholder="Enter your email" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)} 
            required 
            variants={fadeInUp}
          />
          <motion.input 
            className="input-base" 
            type="password" 
            placeholder="Enter your password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            required 
            variants={fadeInUp}
          />
          <motion.button 
            type="submit" 
            disabled={loading} 
            className="btn btn-primary w-full"
            variants={fadeInUp}
          >
            {loading ? <LoadingSpinner size={16} /> : (isSignUp ? "Create Account" : "Sign In")}
          </motion.button>
        </form>
        
        <AnimatePresence>
          {error && (
            <motion.div
              className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-center"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <p className="text-red-400 text-sm">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>
        
        <p className="text-center text-sm text-text-secondary mt-6">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}
          <button 
            onClick={() => setIsSignUp(!isSignUp)} 
            className="btn btn-link text-accent-primary font-medium ml-2"
          >
            {isSignUp ? "Sign In" : "Sign Up"}
          </button>
        </p>
      </motion.div>
    </div>
  );
};

// ==============================================================================
// --- NEW COMPONENT: QuotaExceededModal ---
// This modal provides a polished, user-friendly upgrade prompt.
// ==============================================================================
function QuotaExceededModal({ isOpen, onClose, onUpgrade, userTier }: {
  isOpen: boolean;
  onClose: () => void;
  onUpgrade: () => void;
  userTier: string | null;
}) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="modal-backdrop backdrop-blur-sm flex items-center justify-center"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="modal-panel max-w-md mx-auto text-center"
          variants={scaleIn}
          initial="initial" animate="animate" exit="exit"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-8 space-y-6">
            <div className="flex justify-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-lg shadow-yellow-500/20">
                    <Crown size={32} className="text-white"/>
                </div>
            </div>
            <div className="space-y-3">
                <h3 className="text-2xl font-bold text-text-primary">
                    Daily Limit Reached
                </h3>
                <p className="text-text-secondary">
                    You've used all your daily analyses for the <strong className="text-text-primary">{userTier || 'Free'}</strong> plan. Upgrade your plan to continue working.
                </p>
            </div>
            <div className="flex flex-col gap-3 pt-2">
                <motion.button
                    onClick={onUpgrade}
                    className="btn btn-primary w-full text-base py-3"
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                >
                    <Zap size={16} /> Upgrade Plan
                </motion.button>
                <motion.button
                    onClick={onClose}
                    className="btn btn-secondary w-full"
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                >
                    Maybe Later
                </motion.button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

const OnboardingIdleView = () => {
  const card1Ref = useRef<HTMLDivElement>(null);
  const card2Ref = useRef<HTMLDivElement>(null);
  const card3Ref = useRef<HTMLDivElement>(null);
  const card4Ref = useRef<HTMLDivElement>(null);

  const glow1 = useCursorGlow(card1Ref);
  const glow2 = useCursorGlow(card2Ref);
  const glow3 = useCursorGlow(card3Ref);
  const glow4 = useCursorGlow(card4Ref);
  
  return (
    <motion.div 
      key="idle" 
      className="onboarding-view"
      variants={fadeInUp}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="mb-4">
        <InteractiveBotIcon />
      </div>
      
      <motion.h2
        className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        Welcome to 0Pirate
      </motion.h2>
      
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        Your AI partner for securing and refactoring code. Provide your code and terminal logs, then choose a task to begin.
      </motion.p>
      
      <motion.div 
        className="capability-cards"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div 
          ref={card1Ref} 
          className="capability-card interactive-card group" 
          {...glow1}
          variants={fadeInUp}
          whileHover={{ y: -4, transition: { duration: 0.2 } }}
        >
          <h5 className="flex items-center gap-2">
            <Zap size={16} className="text-yellow-400 group-hover:scale-110 transition-transform" />
            Fix & Secure
          </h5>
          <p>Analyze errors and automatically apply security patches with AI precision.</p>
        </motion.div>
        
        <motion.div 
          ref={card2Ref} 
          className="capability-card interactive-card group" 
          {...glow2}
          variants={fadeInUp}
          whileHover={{ y: -4, transition: { duration: 0.2 } }}
        >
          <h5 className="flex items-center gap-2">
            <HelpCircle size={16} className="text-blue-400 group-hover:scale-110 transition-transform" />
            Code Review
          </h5>
          <p>Get comprehensive AI-powered reviews for best practices and logic improvements.</p>
        </motion.div>
        
        <motion.div 
          ref={card3Ref} 
          className="capability-card interactive-card group" 
          {...glow3}
          variants={fadeInUp}
          whileHover={{ y: -4, transition: { duration: 0.2 } }}
        >
          <h5 className="flex items-center gap-2">
            <FileText size={16} className="text-green-400 group-hover:scale-110 transition-transform" />
            Add Docs
          </h5>
          <p>Generate comprehensive docstrings and comments for better code maintainability.</p>
        </motion.div>
        
        <motion.div 
          ref={card4Ref} 
          className="capability-card interactive-card group" 
          {...glow4}
          variants={fadeInUp}
          whileHover={{ y: -4, transition: { duration: 0.2 } }}
        >
          <h5 className="flex items-center gap-2">
            <Code size={16} className="text-purple-400 group-hover:scale-110 transition-transform" />
            Explain Code
          </h5>
          <p>Receive clear, detailed explanations of complex algorithms and logic patterns.</p>
        </motion.div>
      </motion.div>
    </motion.div>
  );
};

function OllamaSetupModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void; }) {
  const [origin, setOrigin] = useState("");
  const [isSecureContext, setIsSecureContext] = useState(false);
  const [copyStatus, setCopyStatus] = useState("Copy");
  const [activeTab, setActiveTab] = useState("chrome");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setOrigin(window.location.origin);
      setIsSecureContext(window.location.protocol === 'https:');
    }
  }, []);

  const command = `OLLAMA_ORIGINS=${origin} ollama serve`;

  const handleCopy = () => {
    navigator.clipboard.writeText(command).then(() => {
      setCopyStatus("Copied!");
      setTimeout(() => setCopyStatus("Copy"), 2000);
    });
  };
  
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div 
        className="modal-backdrop backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div 
          className="modal-panel max-w-3xl mx-auto mt-20"
          initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-8 space-y-6">
            <div className="text-center">
              <h3 className="text-2xl font-semibold text-text-primary flex items-center justify-center gap-3">
                <Bot size={24} /> Local Ollama Setup
              </h3>
              <p className="text-text-secondary mt-2 max-w-xl mx-auto">
                To use your local models, Ollama must be configured to accept requests from this web application.
              </p>
            </div>
            
            {isSecureContext && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-300 text-sm">
                    <p><strong>Heads up!</strong> Your browser blocks secure websites (like this one) from talking to insecure local servers by default. The steps below explain how to bypass this for development.</p>
                </div>
            )}

            <div className="space-y-4">
              <div>
                <p className="text-text-primary font-medium mb-2">Step 1: Restart your Ollama server with this command.</p>
                <div className="bg-background-light p-4 rounded-lg border border-border-primary flex items-center justify-between gap-4">
                  <pre className="text-sm text-green-400 overflow-x-auto"><code>{command}</code></pre>
                  <button onClick={handleCopy} className="btn btn-secondary text-sm px-3 py-1.5 flex-shrink-0">
                    {copyStatus === "Copy" ? <Clipboard size={14} /> : <ClipboardCheck size={14} className="text-green-400" />}
                    {copyStatus}
                  </button>
                </div>
              </div>
            
              {isSecureContext && (
                <div>
                    <p className="text-text-primary font-medium mb-2">Step 2: Configure your browser to allow mixed content (for advanced users).</p>
                    <div className="border border-border-primary rounded-lg">
                        <div className="flex border-b border-border-primary">
                            <button onClick={() => setActiveTab('chrome')} className={`px-4 py-2 text-sm ${activeTab === 'chrome' ? 'bg-background-light text-white' : 'text-text-secondary'}`}>Chrome / Edge</button>
                            <button onClick={() => setActiveTab('other')} className={`px-4 py-2 text-sm ${activeTab === 'chrome' ? 'text-text-secondary' : 'bg-background-light text-white'}`}>Safari / Firefox</button>
                        </div>
                        <div className="p-4 text-sm text-gray-300">
                            {activeTab === 'chrome' ? (
                                <p>Navigate to <code className="font-mono bg-background-light px-1 py-0.5 rounded">chrome://flags/#unsafely-treat-insecure-origin-as-secure</code>, enable the flag, and add <code className="font-mono bg-background-light px-1 py-0.5 rounded">{origin}</code> to the list. Then, restart your browser.</p>
                            ) : (
                                <p>For browsers like Safari and Firefox, this feature is heavily restricted. The recommended approach is to run the 0Pirate application locally for development, which will allow a direct connection.</p>
                            )}
                        </div>
                    </div>
                </div>
              )}
            </div>
            
            <div className="flex justify-between items-center pt-4">
              <a href="https://github.com/ollama/ollama/blob/main/docs/faq.md#how-can-i-expose-ollama-on-my-network" target="_blank" rel="noopener noreferrer" className="btn btn-link text-accent-primary text-sm flex items-center gap-2">
                Ollama CORS Docs <ExternalLink size={14} />
              </a>
              <motion.button onClick={onClose} className="btn btn-primary" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>Got it</motion.button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function ConfirmationModal({ isOpen, onClose, onConfirm, title, children, promptText, confirmLabel = "Confirm" }: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children: React.ReactNode;
  promptText: string;
  confirmLabel?: string;
}) {
  const [inputValue, setInputValue] = useState("");
  const isMatch = inputValue === promptText;

  useEffect(() => {
    if (isOpen) {
      setInputValue("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div 
        className="modal-backdrop backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div 
          className="modal-panel max-w-md mx-auto mt-20"
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6 space-y-6">
            <div className="text-center">
              <h3 className="text-xl font-semibold text-text-primary">{title}</h3>
            </div>
            
            <div className="text-center text-text-secondary">
              {children}
            </div>
            
            <div className="space-y-3">
              <p className="text-sm text-text-secondary">
                To confirm, please type "<strong className="text-text-primary font-mono">{promptText}</strong>" below:
              </p>
              <input
                type="text"
                className="input-base w-full font-mono"
                placeholder={promptText}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                autoFocus
              />
            </div>
            
            <div className="flex gap-3">
              <motion.button 
                onClick={onClose} 
                className="btn btn-secondary w-full"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                Cancel
              </motion.button>
              <motion.button 
                onClick={onConfirm} 
                disabled={!isMatch} 
                className="btn btn-destructive w-full disabled:opacity-50 disabled:cursor-not-allowed"
                whileHover={isMatch ? { scale: 1.02 } : {}}
                whileTap={isMatch ? { scale: 0.98 } : {}}
              >
                {confirmLabel}
              </motion.button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function ApiKeysView({ token, savedKeys, onKeysChange }: {
    token: string | null;
    savedKeys: { name: string; provider: string }[];
    onKeysChange: () => void;
}) {
    const [provider, setProvider] = useState("gemini");
    const [apiKey, setApiKey] = useState("");
    const [keyName, setKeyName] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [isConfirmModalOpen, setConfirmModalOpen] = useState(false);
    const [keyToDelete, setKeyToDelete] = useState<string | null>(null);
    const [editingKeyName, setEditingKeyName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [actionToken, setActionToken] = useState<string | null>(null);
    const [hasActionToken, setHasActionToken] = useState(false);
    const [isGeneratingToken, setIsGeneratingToken] = useState(false);
    const [showGenerateConfirm, setShowGenerateConfirm] = useState(false);
    const [tokenCopied, setTokenCopied] = useState(false);

    useEffect(() => {
        const checkForToken = async () => {
            if (!token) return;
            try {
                const { data, error } = await supabase.rpc('has_action_token');
                if (error) throw error;
                setHasActionToken(data);
            } catch (e) {
                console.error("Failed to check for action token:", e);
            }
        };
        checkForToken();
    }, [token]);

    const handleGenerateToken = async () => {
        if (!token) return;
        setIsGeneratingToken(true);
        setShowGenerateConfirm(false);
        try {
            const { data, error } = await supabase.rpc('generate_new_action_token');
            if (error) throw error;
            setActionToken(data);
            setHasActionToken(true);
        } catch (e: any) {
            setMessage(`Error generating token: ${e.message}`);
        } finally {
            setIsGeneratingToken(false);
        }
    };

    const handleCopyToken = () => {
        if (!actionToken) return;
        navigator.clipboard.writeText(actionToken).then(() => {
            setTokenCopied(true);
            setTimeout(() => setTokenCopied(false), 2000);
        });
    };

    const saveOrUpdateKey = async () => {
        if (!token || !apiKey) { 
            setMessage("Please provide a non-empty API key."); 
            return; 
        }
        setIsLoading(true);
        const nameToSend = keyName.trim() || provider;
        try {
            const res = await fetch(`${BACKEND_URL}/api/keys`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({ provider, name: nameToSend, api_key: apiKey }),
            });
            if (res.ok) {
                setMessage(editingKeyName ? `✓ Updated key: ${nameToSend}` : `✓ Saved key: ${nameToSend}`);
                resetForm();
                onKeysChange();
            } else {
                const errData = await res.json();
                setMessage(`Failed to save key: ${errData.detail || "Unknown error"}`);
            }
        } catch (e) { 
            console.error("save err", e); 
            setMessage("Error saving key"); 
        } finally {
            setIsLoading(false);
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
                setMessage(`✓ Deleted key: ${nameToDelete}`); 
                onKeysChange(); 
            } else { 
                setMessage("Failed to delete key."); 
            }
        } catch (e) { 
            console.error("delete err", e); 
            setMessage("Error deleting key"); 
        }
    };
    
    const handleDeleteClick = (keyName: string) => {
        setKeyToDelete(keyName);
        setConfirmModalOpen(true);
    };

    const handleConfirmDelete = () => {
        if (keyToDelete) { remove(keyToDelete); }
        setConfirmModalOpen(false);
        setKeyToDelete(null);
    };

    const handleEditClick = (key: { name: string; provider: string }) => {
        setEditingKeyName(key.name);
        setKeyName(key.name);
        setProvider(key.provider);
        setApiKey("");
        setMessage("Editing key. Provide the new API key to update.");
    };

    const resetForm = () => {
        setEditingKeyName(null);
        setKeyName("");
        setProvider("gemini");
        setApiKey("");
        setMessage("");
    };

    return (
        <div className="space-y-8">
            <motion.div 
                className="space-y-6"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
            >
                {/* Add/Edit Key Form */}
                <div className="flex items-center gap-3">
                    <KeyRound size={24} className="text-accent-primary" />
                    <h3 className="text-2xl font-semibold">
                        {editingKeyName ? `Edit '${editingKeyName}'` : "Add New API Key"}
                    </h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-text-secondary">Key Name (Optional)</label>
                        <input className="input-base" type="text" placeholder="e.g., Personal Gemini Key" value={keyName} onChange={(e) => setKeyName(e.target.value)} disabled={!!editingKeyName} />
                    </div>
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-text-secondary">Provider</label>
                        <select className="input-base" value={provider} onChange={(e) => setProvider(e.target.value)} disabled={!!editingKeyName}>
                            {Object.keys(MODEL_OPTIONS).filter((p) => !["auto", "ollama"].includes(p)).map((p) => <option key={p} value={p} className="capitalize">{p}</option>)}
                        </select>
                    </div>
                </div>
                <div className="space-y-3">
                    <label className="text-sm font-medium text-text-secondary">API Key</label>
                    <input className="input-base" type="password" placeholder={editingKeyName ? "Enter new key to update" : "Paste your API key here"} value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                </div>
                <div className="flex gap-3 pt-2">
                    {editingKeyName && <motion.button onClick={resetForm} className="btn btn-secondary flex-1">Cancel Edit</motion.button>}
                    <motion.button onClick={saveOrUpdateKey} disabled={isLoading} className="btn btn-primary flex-1">
                        {isLoading ? <><LoadingSpinner size={14} /> Saving...</> : (editingKeyName ? "Update Key" : "Save Key")}
                    </motion.button>
                </div>
                <AnimatePresence>
                    {message && (
                        <motion.div className={`text-center p-3 rounded-lg border ${message.startsWith('✓') ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                            <p className="text-sm">{message}</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* Saved Keys List */}
            <motion.div className="space-y-2" variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.1 }}>
                <div className="flex items-center gap-3 mb-4">
                    <Settings size={24} className="text-accent-primary" />
                    <h3 className="text-2xl font-semibold">Saved Keys</h3>
                    {savedKeys.length > 0 && (<Badge tone="info">{savedKeys.length} keys</Badge>)}
                </div>
                {savedKeys.length > 0 ? (
                    <div className="flex flex-col">
                        {savedKeys.map((key, index) => (
                            <motion.div key={key.name} className="settings-row py-4 border-b border-border-primary last:border-b-0" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.05 }}>
                                <div className="flex items-center gap-3"><div className="w-2 h-2 bg-accent-primary rounded-full"></div><div><p className="font-mono text-sm font-medium text-text-primary">{key.name}</p><p className="text-xs text-text-secondary capitalize">Provider: {key.provider}</p></div></div>
                                <div className="flex gap-2"><motion.button onClick={() => handleEditClick(key)} className="btn btn-secondary text-sm px-3 py-1.5"><Edit size={14}/> Edit</motion.button><motion.button onClick={() => handleDeleteClick(key.name)} className="btn btn-destructive text-sm px-3 py-1.5"><Trash2 size={14}/> Delete</motion.button></div>
                            </motion.div>
                        ))}
                    </div>
                ) : (
                    <motion.div className="text-center py-12 px-6 border border-dashed border-border-primary rounded-xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                        <KeyRound size={48} className="mx-auto text-text-secondary mb-4" /><p className="text-text-secondary text-lg mb-2">No API keys saved yet</p><p className="text-text-secondary/70 text-sm">Add your first API key to get started...</p>
                    </motion.div>
                )}
            </motion.div>

            {/* GitHub Action Integration Section */}
            <motion.div className="space-y-4" variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.2 }}>
                <div className="flex items-center gap-3 mb-4">
                    <Github size={24} className="text-accent-primary" />
                    <h3 className="text-2xl font-semibold">GitHub Action Integration</h3>
                </div>
                <div className="card p-6 space-y-4">
                    <p className="text-text-secondary">Generate a secure token to authenticate the 0pirate GitHub Action with your account.</p>
                    {actionToken ? (
                        <div className="space-y-4">
                            <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-300 text-sm"><strong>Important:</strong> Copy this token now. You will not be able to see it again.</div>
                            <div className="bg-background-light p-4 rounded-lg border border-border-primary flex items-center justify-between gap-4">
                                <pre className="text-sm text-text-primary overflow-x-auto font-mono">{actionToken}</pre>
                                <button onClick={handleCopyToken} className="btn btn-secondary text-sm px-3 py-1.5 flex-shrink-0">
                                    {tokenCopied ? <ClipboardCheck size={14} className="text-green-400" /> : <Clipboard size={14} />} {tokenCopied ? "Copied!" : "Copy"}
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-between">
                            {hasActionToken ? (<p className="text-sm text-green-400 flex items-center gap-2"><ShieldCheck size={16} /> An Action Token is configured.</p>) : (<p className="text-sm text-text-secondary">No token generated yet.</p>)}
                            <motion.button onClick={() => setShowGenerateConfirm(true)} disabled={isGeneratingToken} className="btn btn-primary">
                                {isGeneratingToken ? <><LoadingSpinner size={14} /> Generating...</> : (hasActionToken ? 'Generate New Token' : 'Generate Token')}
                            </motion.button>
                        </div>
                    )}
                </div>
            </motion.div>
            
            <ConfirmationModal isOpen={isConfirmModalOpen} onClose={() => setConfirmModalOpen(false)} onConfirm={handleConfirmDelete} title="Delete API Key" promptText={keyToDelete || ""} confirmLabel="Delete Key">
                <p>This action will permanently delete the <strong className="text-red-400">{keyToDelete}</strong> API key.</p>
            </ConfirmationModal>

            <ConfirmationModal isOpen={showGenerateConfirm} onClose={() => setShowGenerateConfirm(false)} onConfirm={handleGenerateToken} title="Generate New Action Token" promptText="generate" confirmLabel="Generate">
                {hasActionToken ? (<p>This will invalidate your existing token. Confirm by typing "<strong className="text-amber-400">generate</strong>" below.</p>) : (<p>This will create a new token. Confirm by typing "<strong className="text-amber-400">generate</strong>" below.</p>)}
            </ConfirmationModal>
        </div>
    );
}

function AccountManager({ token, email, savedKeys, onKeysChange, onClose, userTier, onUpgrade, activeView, setActiveView }: {
  token: string | null; email: string | undefined; savedKeys: { name: string; provider: string }[]; onKeysChange: () => void;
  onClose: () => void; userTier: string | null; onUpgrade: () => void; activeView: string; setActiveView: (view: string) => void;
}) {
  const getTierBadgeProps = (tier: string | null) => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      case 'developer': return { tone: 'info', children: 'Developer Plan' };
      case 'professional': return { tone: 'info', children: 'Professional Plan' };
      case 'enterprise': return { tone: 'success', children: 'Enterprise' };
      default: return { tone: 'free', children: 'Free Plan' }; // Use the new 'free' tone
    }
};

  const navItems = [{ id: 'account', label: 'Account', icon: User }, { id: 'api_keys', label: 'API Keys', icon: KeyRound }];

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    onClose();
  };

  return (
    <motion.div className="modal-panel" variants={scaleIn} initial="initial" animate="animate" exit="exit">
        <div className="settings-header">
            <motion.button onClick={onClose} className="btn btn-secondary" whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <ChevronLeft size={16} /> Back to Dashboard
            </motion.button>
        </div>
        <div className="settings-modal-layout">
            <nav className="settings-sidebar">
                {navItems.map((item, index) => (
                    <motion.button 
                        key={item.id}
                        className="settings-nav-item" 
                        data-active={activeView === item.id} 
                        onClick={() => setActiveView(item.id)}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        <item.icon size={16} /> {item.label}
                    </motion.button>
                ))}
            </nav>
            <main className="settings-content">
                <AnimatePresence mode="wait">
                    {activeView === 'account' && (
    <motion.div 
        key="account" 
        variants={fadeInUp} 
        initial="initial" 
        animate="animate" 
        exit={{ opacity: 0, transition: { duration: 0.1 } }} 
        className="space-y-8"
    >
        {/* Section 1: Account Information */}
        <div className="settings-section">
            <h3 className="flex items-center gap-3"><User size={24} className="text-accent-primary" /> Account Information</h3>
            <div className="settings-row mt-6 py-2"> {/* Added py-2 */}
                <div className="settings-row-info">
                    <label>Email Address</label>
                    <p className="font-mono text-text-secondary">{email}</p>
                </div>
            </div>
        </div>

        {/* Section 2: Subscription */}
        <div className="settings-section">
    <h3 className="flex items-center gap-3"><Zap size={24} className="text-accent-primary" /> Subscription</h3>
    <div className="settings-row mt-6 py-4">
        <div className="settings-row-info">
            <label>Current Plan</label>
            <div className="mt-1">
                {(() => {
                    const tierDisplay = getTierBadgeProps(userTier);
                    if (typeof tierDisplay === 'string') {
                        return <p className="text-lg font-semibold text-gray-200">{tierDisplay}</p>;
                    }
                    return <Badge {...tierDisplay} />;
                })()}
            </div>
        </div>
        <motion.button onClick={onUpgrade} className="btn btn-primary" whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            Upgrade Plan
        </motion.button>
    </div>
</div>

        {/* Section 3: Account Actions */}
        <div className="settings-section">
            <h3 className="flex items-center gap-3"><Settings size={24} className="text-accent-primary" /> Account Actions</h3>
            <div className="settings-row mt-6 py-2"> {/* Added py-2 */}
                <div className="settings-row-info">
                    <label>Sign Out</label>
                    <p className="text-sm text-text-secondary">You will be returned to the login screen.</p>
                </div>
                <motion.button onClick={handleSignOut} className="btn btn-secondary" whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                    <LogOut size={16} /> Sign Out
                </motion.button>
            </div>
        </div>
    </motion.div>
)}
                    {activeView === 'api_keys' && (<ApiKeysView token={token} savedKeys={savedKeys} onKeysChange={onKeysChange} />)}
                </AnimatePresence>
            </main>
        </div>
    </motion.div>
  );
}

const detectApiKeyProvider = (key: string): string => {
  if (key.startsWith("sk-proj-")) return "openai";
  if (key.startsWith("sk-")) return "anthropic";
  if (key.length > 35 && key.length < 45 && !key.includes("-")) return "gemini";
  return "unknown";
};

function GuestApiKeyInput({ apiKey, setApiKey, setProvider }: {
  apiKey: string;
  setApiKey: (key: string) => void;
  setProvider: (provider: string) => void;
}) {
  const [detectedProvider, setDetectedProvider] = useState("unknown");

  useEffect(() => {
    const provider = detectApiKeyProvider(apiKey);
    setDetectedProvider(provider);
    if (provider !== "unknown") {
      setProvider(provider);
    }
  }, [apiKey, setProvider]);

  const providerInfo = {
    openai: { icon: <Bot size={16} className="text-green-400" />, name: "OpenAI" },
    anthropic: { icon: <Bot size={16} className="text-orange-400" />, name: "Anthropic" },
    gemini: { icon: <Zap size={16} className="text-blue-400" />, name: "Gemini" },
    unknown: { icon: <KeyRound size={16} className="text-text-secondary" />, name: "" },
  };

  const currentProvider = providerInfo[detectedProvider as keyof typeof providerInfo] || providerInfo.unknown;

  return (
    <div className="relative">
      <input
        type="password"
        className="input-base font-mono transition-all duration-200 focus:ring-2 focus:ring-blue-500/30 pl-10"
        placeholder="Paste your API key here to run"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
      />
      <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center gap-2 text-xs font-semibold">
        {currentProvider.icon}
        {currentProvider.name && (
          <span className="text-text-secondary">{currentProvider.name}</span>
        )}
      </div>
    </div>
  );
}

function ToggleSwitch({
  label,
  description,
  activeInfo,
  accentColor,
  checked,
  onChange,
  icon: Icon
}: {
  label: string;
  description: string;
  activeInfo: string;
  accentColor: 'green' | 'blue';
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon?: React.ElementType;
}) {
  const activeColor = accentColor === 'green' ? '#22C55E' : 'var(--accent-primary)';

  return (
    <div
      className="toggle-card-enhanced"
      data-active={checked}
      data-accent={accentColor}
      style={{ borderColor: checked ? activeColor : 'var(--border-primary)' }}
    >
      <div className="flex justify-between items-start">
        <div className="toggle-switch-info flex-grow">
          <h5 className="font-semibold" style={{ color: checked ? activeColor : 'var(--text-primary)' }}>
            {label}
          </h5>
          <p className="text-sm text-text-secondary">{description}</p>
        </div>
        <div className="switch relative ml-4">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            className="sr-only"
          />
          <motion.div
            className="slider"
            onClick={() => onChange(!checked)}
            animate={{ backgroundColor: checked ? activeColor : 'var(--background-light)' }}
          >
            <motion.span
              className="slider-thumb"
              animate={{ x: checked ? 18 : 0 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
            />
          </motion.div>
        </div>
      </div>
      <AnimatePresence>
        {checked && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: 'auto', marginTop: '1rem' }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
          >
            <p className="toggle-active-info" style={{ color: activeColor }}>
              {Icon && <Icon size={16} />} {activeInfo}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


function restoreFromMaps(
    abstractedCode: Record<string, string>,
    secretMaps: Record<string, Record<string, string>>,
    abstractionMaps: Record<string, Record<string, string>>
): Record<string, string> {
    const restoredFiles: Record<string, string> = {};

    for (const path in abstractedCode) {
        let content = abstractedCode[path];
        
        // --- THIS IS THE CORRECTED LOGIC ---
        const reverseMap: Record<string, string> = {};

        // 1. Process abstraction_maps (structure: original -> placeholder)
        const abstractionMapForFile = abstractionMaps[path] || {};
        for (const original in abstractionMapForFile) {
            const placeholder = abstractionMapForFile[original];
            reverseMap[placeholder] = original;
        }

        // 2. Process secret_maps (structure: placeholder -> original)
        const secretMapForFile = secretMaps[path] || {};
        for (const placeholder in secretMapForFile) {
            const original = secretMapForFile[placeholder];
            reverseMap[placeholder] = original;
        }
        // --- END OF CORRECTION ---

        // Sort placeholders by length, descending, to prevent partial replacements.
        const sortedPlaceholders = Object.keys(reverseMap).sort((a, b) => b.length - a.length);

        for (const placeholder of sortedPlaceholders) {
            // Escape regex special characters in the placeholder
            const escapedPlaceholder = placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            // Use RegExp to replace all occurrences globally
            content = content.replace(new RegExp(escapedPlaceholder, 'g'), reverseMap[placeholder]);
        }
        
        restoredFiles[path] = content;
    }

    return restoredFiles;
}

type RestorationMaps = {
  secret_maps: Record<string, Record<string, string>>;
  abstraction_maps: Record<string, Record<string, string>>;
};

function MainApp({ token, savedKeys, onGuestQuotaExceeded, onUserQuotaExceeded }: {
  token: string | null;
  savedKeys: { name: string; provider: string }[];
  onGuestQuotaExceeded: () => void;
  onUserQuotaExceeded: () => void;
}) {
  type ViewState = JobStatus;
  const [pastedCode, setPastedCode] = useState("");
  const [errorLog, setErrorLog] = useState("");
  const [task, setTask] = useState("fix_and_secure");
  const [userPrompt, setUserPrompt] = useState(""); // NEW state for generate_code
  const [languageHint, setLanguageHint] = useState("");
  const [result, setResult] = useState<ResultShape | null>(null);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [status, setStatus] = useState("Select a task, provide code, and run the analysis.");
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-1.5-pro");
  const [jobId, setJobId] = useState<string | null>(null);
  const [tokenSaver, setTokenSaver] = useState(false);
  const [maxSecurity, setMaxSecurity] = useState(true);
  const [copyOK, setCopyOK] = useState("");
  const [view, setView] = useState<ViewState>("idle");
  const [selectedKeyName, setSelectedKeyName] = useState("");
  const [guestApiKey, setGuestApiKey] = useState("");
  const [inputMode, setInputMode] = useState<'paste' | 'upload'>('paste');
  const [files, setFiles] = useState<File[]>([]);
  const [showOllamaHelp, setShowOllamaHelp] = useState(false);
  const [allowList, setAllowList] = useState("");
  const [restorationMaps, setRestorationMaps] = useState<RestorationMaps | null>(null);


  const getLanguageFromFileName = (filename: string | null): string => {
    if (!filename) return 'plaintext';
    
    const extension = filename.split('.').pop()?.toLowerCase();

    switch (extension) {
      case 'js':
      case 'jsx':
        return 'javascript';
      case 'ts':
      case 'tsx':
        return 'typescript';
      case 'py':
        return 'python';
      case 'css':
        return 'css';
      case 'html':
        return 'html';
      case 'json':
        return 'json';
      case 'md':
        return 'markdown';
      case 'sh':
      case 'bash':
        return 'bash';
      case 'java':
        return 'java';
      case 'cpp':
        return 'cpp';
      case 'c':
        return 'c';
      case 'go':
        return 'go';
      case 'rb':
          return 'ruby';
      default:
        return 'plaintext';
    }
  };

  const language = getLanguageFromFileName(activeFile);

  const onDrop = useCallback((acceptedFiles: File[]) => { 
    setFiles(prevFiles => [...prevFiles, ...acceptedFiles]); 
    setInputMode("upload"); 
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  const success = useCallback((d: any) => {
    let resultDataAbstracted = d.result || {};
    
    // Attempt to parse the result if it's a string, as before
    if (typeof resultDataAbstracted === 'string') {
      try { resultDataAbstracted = JSON.parse(resultDataAbstracted); } 
      catch (e) {
        console.error("Failed to parse result JSON:", e);
        setResult({ ...d, result: { notice: resultDataAbstracted } });
        setView("result");
        return;
      }
    }

    // This is the critical new logic:
    if (restorationMaps) {
        // If we have maps, perform the client-side restoration
        const restoredResult = restoreFromMaps(
            resultDataAbstracted as Record<string, string>,
            restorationMaps.secret_maps,
            restorationMaps.abstraction_maps
        );
        
        let firstFileName = Object.keys(restoredResult).length > 0 ? Object.keys(restoredResult)[0] : null;

        setResult({ ...d, result: restoredResult });
        setActiveFile(firstFileName);
    } else {
        // Fallback for flows that don't use restoration (like Ollama)
        const firstFileName = Object.keys(resultDataAbstracted).length > 0 ? Object.keys(resultDataAbstracted)[0] : null;
        setResult({ ...d, result: resultDataAbstracted });
        setActiveFile(firstFileName);
    }
    
    setView("result");
    setStatus("Analysis completed successfully");
    setRestorationMaps(null); // Securely clear the sensitive maps from state after use
  }, [restorationMaps]); // Add restorationMaps to the dependency array

  const fail = useCallback((err: string) => {
    // --- THIS IS THE FIX for "err.toLowerCase is not a function" ---
    // Convert `err` to a string *before* calling .toLowerCase()
    // This safely handles Error objects, strings, or any other type.
    const errString = String(err);
    const isQuotaError = errString?.toLowerCase().includes("quota") || errString?.toLowerCase().includes("limit");
    // --- END OF FIX ---

    if (isQuotaError) {
      // It's a quota error, trigger the specific handlers
      if (!token) {
        onGuestQuotaExceeded(); // This shows the Auth (Sign Up) page
      } else {
        onUserQuotaExceeded(); // This will show our new Quota Modal
      }
      // Reset the main view to idle so the user isn't stuck on a loading screen
      setView("idle");
    } else {
      // It's a genuine error, show the error view
      setResult({ notice: `Error: ${errString}` });
      setView("error");
      setStatus("Analysis failed");
    }
  }, [token, onGuestQuotaExceeded, onUserQuotaExceeded]);
  
  useJobPolling(jobId, token, success, fail, setStatus);

  useEffect(() => {
    if (savedKeys) {
      const keysForProvider = savedKeys.filter(k => k.provider === provider);
      setSelectedKeyName(keysForProvider.length > 0 ? keysForProvider[0].name : "");
    }
  }, [provider, savedKeys]);

async function createTamperEvidentHash(files: File[], pastedCode: string): Promise<string> {
    // We'll hash either the uploaded files or the pasted code
    let combinedContent = "";
    
    if (files.length > 0) {
        // To ensure consistency, sort files by name before concatenating
        const sortedFiles = [...files].sort((a, b) => a.name.localeCompare(b.name));
        for (const file of sortedFiles) {
            combinedContent += await file.text();
        }
    } else {
        combinedContent = pastedCode;
    }

    const encoder = new TextEncoder();
    const data = encoder.encode(combinedContent);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    
    // Convert buffer to hex string
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
}

   
  const submit = async () => {
    if (task === "generate_code") {
      if (!userPrompt.trim()) return fail("Please provide a prompt to generate code.");
      // Code/Files are optional context for generation, not required.
    } else {
      // For all other tasks, code/files are required.
      if (!pastedCode.trim() && files.length === 0) return fail("Please paste or upload your code.");
    }
    // Error log is only strictly required for fix_and_secure
    if (task === "fix_and_secure" && !errorLog.trim()) return fail("Please paste the error log for fixing.");
  
    setView("loading");
    setResult(null);
    setJobId(null);
    setRestorationMaps(null); // Clear previous maps
    setStatus("Submitting analysis request...");

    // OLLAMA (Local LLM) flow remains the same, as it doesn't need the secure redactor.
    if (provider === 'ollama') {
      try {
        setStatus("Connecting to local LLM...");
        let promptContent = "";
        if (task === "generate_code") {
           promptContent = userPrompt; // Use user prompt directly for Ollama generation
        } else {
            promptContent = `Task: ${task}\n\n`;
            if (files.length > 0) {
                const fileContent = await files[0].text(); // Simple case for Ollama, maybe handle multiple later
                promptContent += `File: ${files[0].name}\n---\n${fileContent}`;
            } else {
                promptContent += `Code:\n---\n${pastedCode}`;
            }
            if(errorLog) {
                promptContent += `\n\nError Log:\n---\n${errorLog}`;
            }
        }

        const ollamaResponse = await fetch('http://localhost:11434/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: model, prompt: promptContent, stream: false }),
        });

        if (!ollamaResponse.ok) throw new Error(`Ollama server responded with status ${ollamaResponse.status}.`);
        const ollamaResult = await ollamaResponse.json();
        const formattedResult = { result: { "Ollama Response.md": ollamaResult.response }, analysis: "Analysis completed using your local Ollama instance." };
        success(formattedResult);

      } catch (e: any) {
        fail(`Connection failed. Please open the "Setup" guide for instructions.`);
      }
      return;
    }

    // API Key checks (remain the same)
    const requiresKey = !['auto'].includes(provider);
    if (requiresKey) {
      if (token && !selectedKeyName) return fail(`Please select a saved API key for '${provider}' in your account settings.`);
      if (!token && !guestApiKey.trim()) return fail(`Please provide an API key for '${provider}' to continue.`);
    }

    try {
        // STEP 1: Client-side Redaction
        setStatus("Securing code (client-side redaction)...");
        const redactionFormData = new FormData();
        let hasFilesToRedact = false;

        // **CORRECTION START**: Include files for ALL tasks (including generate_code context) in redaction
        if (files.length > 0) {
            files.forEach(file => redactionFormData.append("files", file, file.name));
            hasFilesToRedact = true;
        } else if (pastedCode.trim() && task !== "generate_code") { // Only redact pasted code if not generate_code
            redactionFormData.append("files", new Blob([pastedCode]), "pasted_code.py");
            hasFilesToRedact = true;
        } else if (task !== "generate_code" && files.length === 0 && !pastedCode.trim()) {
             return fail("No code provided for redaction.");
        }
        // **CORRECTION END**

        if (allowList.trim()) {
            const allowListArray = allowList.split(',').map(item => item.trim()).filter(Boolean);
            redactionFormData.append("allow_list_json", JSON.stringify(allowListArray));
        }

        // Only call redact if there are actual files/code to process
        let redactionData = { abstracted_files: {}, secret_maps: {}, abstraction_maps: {} };
        if (hasFilesToRedact) { // Use the flag here
            const redactRes = await fetch(`${BACKEND_URL}/api/redact`, {
                method: "POST",
                body: redactionFormData,
            });

            if (!redactRes.ok) {
                const err = await redactRes.json();
                throw new Error(`Redaction failed: ${err.detail || 'Server error'}`);
            }
            redactionData = await redactRes.json();
        }

        const { abstracted_files, secret_maps, abstraction_maps } = redactionData;
        setRestorationMaps({ secret_maps, abstraction_maps }); // Store maps for potential restoration

        // STEP 2: Call /api/process_code with ABSTRACTED data
        setStatus("Submitting analysis request...");
        const mainFormData = new FormData();
        const abstractedFileEntries = Object.entries(abstracted_files);

        // Add abstracted files (could be original code OR context files) to the main form data
        if (abstractedFileEntries.length > 0) {
            for (const [path, content] of abstractedFileEntries) {
                mainFormData.append("files", new Blob([content as string]), path);
            }

            const abstractedContentString = abstractedFileEntries.sort((a,b) => a[0].localeCompare(b[0])).map(entry => entry[1]).join('');
            const encoder = new TextEncoder();
            const data = encoder.encode(abstractedContentString);
            // !! FIX: This must be SHA-256 !!
            const hashBuffer = await crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            mainFormData.append("tamper_evident_hash", hashHex);

        } else if (task !== "generate_code") {
             // If not generating code and no files ended up here after redaction, error
             return fail("Failed to prepare abstracted code for submission.");
        
        } else if (task === "generate_code" && abstractedFileEntries.length === 0) {
            // [Production Fix] explicitly append empty hash string for Generate Code tasks
            // with no context files, satisfying the backend integrity check.
            mainFormData.append("tamper_evident_hash", "");
        }
      
        // Append other form data
        mainFormData.append("task", task);
        if (errorLog) mainFormData.append("error_log", errorLog);
        mainFormData.append("provider", provider);
        if (model) mainFormData.append("model", model);
        if (token && selectedKeyName) mainFormData.append("api_key_name", selectedKeyName);
        else if (!token && guestApiKey) mainFormData.append("api_key", guestApiKey);
        mainFormData.append("token_saver_enabled", String(tokenSaver));
        mainFormData.append("cove_hardening_enabled", String(maxSecurity));
        
        // --- THIS IS THE FIX ---
        // We were missing cove_hardening_enabled, causing a 422 error
        mainFormData.append("cove_hardening_enabled", String(maxSecurity));
        // --- END OF FIX ---


        // Append generate_code specific fields
        if (task === "generate_code") {
            mainFormData.append("user_prompt", userPrompt);
            if (languageHint) mainFormData.append("language_hint", languageHint);
        }

        // Send request
        const headers: HeadersInit = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const mainRes = await fetch(`${BACKEND_URL}/api/process_code`, {
            method: "POST",
            headers,
            body: mainFormData,
        });

        const d = await mainRes.json();
        if (mainRes.ok) {
            setJobId(d.job_id);
            setStatus("Job submitted, processing...");
        } else {
            // Handle 422 errors by parsing the list
            if (mainRes.status === 422 && d.detail && Array.isArray(d.detail)) {
                const errorMsg = d.detail.map((err: any) => `${err.loc.join(' -> ')}: ${err.msg}`).join(', ');
                fail(`Validation Error: ${errorMsg}`);
            } else {
                fail(d.detail || "Submission failed.");
            }
        }

    } catch (e: any) {
        fail(e.message || "A network error occurred.");
    }
  };

  const copy = (textToCopy?: string) => {
    let text = textToCopy || "";
    if (!text && result?.result) {
      if (typeof result.result === "string") text = result.result;
      else if (typeof result.result === "object" && activeFile) text = (result.result as Record<string, string>)[activeFile] || "";
    }
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopyOK("Copied!");
      setTimeout(() => setCopyOK(""), 2000);
    });
  };

  const resetAll = () => {
    setPastedCode("");
    setErrorLog("");
    setResult(null);
    setView("idle");
    setStatus("Select a task, provide code, and run the analysis.");
    setFiles([]); // Clear uploaded files
    setUserPrompt(""); // Clear generate prompt
    setLanguageHint(""); // Clear language hint
    setJobId(null);
    setRestorationMaps(null);
  };

  useEffect(() => { 
    const models = MODEL_OPTIONS[provider] || ["(auto-select)"]; 
    setModel(models[0]); 
  }, [provider]);
  
  const resultData = result?.result || {};
  const activeFileContent = activeFile && typeof resultData === "object" ? (resultData as Record<string, string>)[activeFile] : (typeof resultData === "string" ? resultData : "");

  const taskOptions = [
    { value: "fix_and_secure", label: "Fix & Secure", icon: Zap },
    { value: "generate_tests", label: "Generate Tests", icon: FlaskConical }, 
    { value: "generate_code", label: "Generate Code", icon: Box },
    { value: "code_review", label: "Code Review", icon: HelpCircle },
    { value: "documentation", label: "Add Documentation", icon: FileText },
    { value: "refactor", label: "Refactor", icon: Code },
    { value: "explain", label: "Explain Code", icon: Terminal }
  ];

  return (
    <>
    <OllamaSetupModal isOpen={showOllamaHelp} onClose={() => setShowOllamaHelp(false)} />
    <main className="content-grid flex-grow">
      <div className="left-pane flex flex-col gap-6">
        <div className="flex-grow space-y-6 overflow-y-auto pr-2">
          <motion.div 
            className="space-y-6"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={fadeInUp}>
              {task === 'generate_code' ? (
                // --- UI for Generate Code Task ---
                <div className="space-y-6">
                   <div className="code-wrapper group">
                     <h4 className="flex items-center gap-2 group-hover:text-accent-primary transition-colors">
                       <MessageSquare size={16} />
                       Your Prompt
                     </h4>
                     <textarea
                       className="code-input resize-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                       placeholder="Describe the code you want to generate (e.g., 'Create a Python function to calculate factorial')..."
                       value={userPrompt}
                       onChange={(e) => setUserPrompt(e.target.value)}
                       rows={6} // Make prompt area larger
                     />
                   </div>
                   <div className="code-wrapper group">
                     <h4 className="flex items-center gap-2 group-hover:text-accent-primary transition-colors">
                       <Code size={16} />
                       Language Hint (Optional)
                     </h4>
                     <input
                       type="text"
                       className="input-base"
                       placeholder="e.g., python, javascript, html"
                       value={languageHint}
                       onChange={(e) => setLanguageHint(e.target.value)}
                      />
                   </div>
                    {/* Optional Context Upload */}
                    <div
                      {...getRootProps()}
                      className={`code-wrapper group flex flex-col items-center justify-center text-center border-dashed border-2 hover:border-accent-primary transition-all cursor-pointer min-h-[150px] ${isDragActive ? 'border-accent-primary' : 'border-border-primary'}`}
                    >
                        <input {...getInputProps()} />
                        <UploadCloud size={24} className="text-text-secondary mb-3" />
                        <p className="font-semibold text-sm">Add Context Files (Optional)</p>
                        <p className="text-xs text-text-secondary">{isDragActive ? "Drop files now..." : "Drag & drop or click to upload relevant files"}</p>
                        {files.length > 0 && (
                            <div className="mt-3 text-left w-full text-xs">
                                <h5 className="font-semibold uppercase text-text-secondary">Context Files:</h5>
                                <ul className="space-y-1 mt-1 max-h-20 overflow-y-auto"> {/* Added max-h and scroll */}
                                    {files.map(file => (<li key={file.name} className="truncate">- {file.name}</li>))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>
                // --- END UI for Generate Code Task ---
              ) : (
                // --- UI for Other Tasks (Code/Log Input) ---
                <>
              <div className="flex gap-2 mb-4">
                  <motion.button 
                      onClick={() => setInputMode('paste')}
                      className={`btn flex-1 ${inputMode === 'paste' ? 'btn-primary' : 'btn-secondary'}`}
                      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  >
                      Paste Code
                  </motion.button>
                  <motion.button 
                      onClick={() => setInputMode('upload')}
                      className={`btn flex-1 ${inputMode === 'upload' ? 'btn-primary' : 'btn-secondary'}`}
                      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  >
                      Upload Files / ZIP
                  </motion.button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {inputMode === 'paste' ? (
                  <div className="code-wrapper group lg:col-span-2">
                     <h4 className="flex items-center gap-2 group-hover:text-accent-primary transition-colors">
                       <Clipboard size={16} />
                       Paste Your Code
                     </h4>
                     <textarea 
                       className="code-input resize-none focus:ring-2 focus:ring-blue-500/20 transition-all" 
                       placeholder="Paste your buggy code here..." 
                       value={pastedCode} 
                       onChange={(e) => setPastedCode(e.target.value)} 
                     />
                  </div>
                ) : (
                  <div 
                      {...getRootProps()} 
                      className={`code-wrapper group flex flex-col items-center justify-center text-center border-dashed border-2 hover:border-accent-primary transition-all cursor-pointer ${isDragActive ? 'border-accent-primary' : 'border-border-primary'}`}
                  >
                      <input {...getInputProps()} />
                      <Bot size={32} className="text-text-secondary mb-4" />
                      <p className="font-semibold">{isDragActive ? "Drop files now..." : "Drag & drop files or a .zip here"}</p>
                      <p className="text-sm text-text-secondary">or click to select files</p>
                      {files.length > 0 && (
                          <div className="mt-4 text-left w-full">
                              <h5 className="font-semibold text-xs uppercase text-text-secondary">Selected Files:</h5>
                              <ul className="text-sm space-y-1 mt-2">
                                  {files.map(file => (
                                      <li key={file.name} className="truncate">- {file.name}</li>
                                  ))}
                              </ul>
                          </div>
                      )}
                  </div>
                )}

                <div className="code-wrapper group">
                   <h4 className="flex items-center gap-2 group-hover:text-accent-primary transition-colors">
                     <Terminal size={16} />
                     Terminal Log
                   </h4>
                   <textarea 
                     className="terminal-input resize-none focus:ring-2 focus:ring-blue-500/20 transition-all" 
                     placeholder="Paste terminal output, stack traces, errors here..." 
                     value={errorLog} 
                     onChange={(e) => setErrorLog(e.target.value)} 
                   />
                </div>
              </div>
              </>
              )}
            </motion.div>

            <motion.div className="card space-y-6" variants={fadeInUp}>
              <div className="space-y-3">
                <label className="text-sm font-medium text-text-secondary flex items-center gap-2">
                  <Settings size={16} /> Task Selection
                </label>
                <select
                  className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30"
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                >
                  {taskOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                       {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <label className="text-sm font-medium text-text-secondary">Provider</label>
                  <select 
                    className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                    value={provider} 
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    {Object.keys(MODEL_OPTIONS).map((p) => (
                      <option key={p} value={p} className="capitalize">{p}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-sm font-medium text-text-secondary">Model</label>
                    {provider === 'ollama' && (
                      <button 
                        onClick={() => setShowOllamaHelp(true)}
                        className="btn btn-link text-xs text-accent-primary flex items-center gap-1"
                      >
                        <HelpCircle size={14} />
                        Setup
                      </button>
                    )}
                  </div>
                  <select 
                    className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                    value={model} 
                    onChange={(e) => setModel(e.target.value)} 
                    disabled={(MODEL_OPTIONS[provider] || []).length <= 1}
                  >
                    {(MODEL_OPTIONS[provider] || []).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>

              {provider !== 'auto' && provider !== 'ollama' && (
                <div className="space-y-3">
                  <label className="text-sm font-medium text-text-secondary">API Key</label>
                  {token ? (
                    <select 
                      className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                      value={selectedKeyName} 
                      onChange={(e) => setSelectedKeyName(e.target.value)} 
                      disabled={savedKeys.filter(k => k.provider === provider).length === 0}
                    >
                      {savedKeys.filter(k => k.provider === provider).length === 0 ? 
                        (<option value="">Go to Account to add a key</option>) : 
                        (savedKeys.filter(key => key.provider === provider).map((key) => (
                          <option key={key.name} value={key.name}>{key.name}</option>
                        )))
                      }
                    </select>
                  ) : (
                    <GuestApiKeyInput 
                      apiKey={guestApiKey} 
                      setApiKey={setGuestApiKey} 
                      setProvider={setProvider} 
                    />
                  )}
                </div>
              )}
            </motion.div>

            <motion.div className="card space-y-4" variants={fadeInUp}>
               <h4 className="flex items-center gap-3 font-semibold text-text-primary">
                  <ShieldCheck size={18}/> Privacy & Security
               </h4>
               <ToggleSwitch 
                 label="Max Security" 
                 description="Zero-knowledge processing." 
                 activeInfo="Secure mode activated - All data is abstracted."
                 accentColor="green"
                 checked={maxSecurity} 
                 onChange={setMaxSecurity} 
                 icon={ShieldCheck} 
               />
               <ToggleSwitch 
                 label="Token Saver (DIFF)" 
                 description="Output changes only." 
                 activeInfo="Optimizing token usage for efficiency."
                 accentColor="blue"
                 checked={tokenSaver} 
                 onChange={setTokenSaver} 
                 icon={Zap} 
               />

               {/* --- ADD THIS NEW BLOCK FOR THE ALLOW LIST --- */}
                <div className="space-y-4 pt-5 border-t border-border-secondary">
                    <label className="text-sm font-medium text-text-secondary flex items-center gap-2">
                        <Edit size={16} />
                        Granular Controls (Optional)
                    </label>
                    <textarea
                        className="input-base w-full transition-all duration-200 focus:ring-2 focus:ring-blue-500/30 font-mono text-xs"
                        placeholder="Enter comma-separated words to keep (e.g., myApi, calculateTotal, React)"
                        value={allowList}
                        onChange={(e) => setAllowList(e.target.value)}
                        rows={3}
                    />
                    <p className="text-xs text-text-secondary/80">
                        Identifiers listed here will not be abstracted. Useful for preserving public function names or specific library keywords.
                    </p>
                </div>
            </motion.div>
          </motion.div>
        </div>
        
        <motion.div 
          className="grid grid-cols-2 gap-4 flex-shrink-0"
          variants={fadeInUp}
        >
          <motion.button 
            onClick={submit} 
            disabled={view === "loading"} 
            className={`btn btn-primary w-full ${view === "loading" ? "btn-loading" : ""}`}
            whileHover={{ scale: view === "loading" ? 1 : 1.02 }}
            whileTap={{ scale: view === "loading" ? 1 : 0.98 }}
          >
            {view === "loading" ? (
              <>
                <LoadingSpinner size={16} />
                Running Analysis...
              </>
            ) : (
              <>
                <Zap size={16} />
                Run Analysis
              </>
            )}
          </motion.button>
          
          <motion.button 
            onClick={resetAll} 
            className="btn btn-secondary w-full"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <X size={16} />
            Reset
          </motion.button>
        </motion.div>
      </div>
      
      <aside className="right-pane">
        <div className="card h-full min-h-[600px] overflow-hidden">
            <AnimatePresence mode="wait">
              {view === 'idle' && <OnboardingIdleView />}
              
              {view === 'loading' && (
                <motion.div 
                  key="loading" 
                  className="flex flex-col items-center justify-center h-full text-center space-y-6"
                  variants={fadeInUp}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                   <Bot size={48} className="text-accent-primary" />
                   
                   <div className="space-y-3">
                     <h3 className="text-lg font-semibold">Processing Your Code</h3>
                     <motion.p 
                       className="text-text-secondary"
                       key={status}
                       initial={{ opacity: 0, y: 5 }}
                       animate={{ opacity: 1, y: 0 }}
                     >
                       {status}
                     </motion.p>
                   </div>
                   
                   <div className="w-full max-w-xs">
                     <div className="bg-background-light h-2 rounded-full overflow-hidden">
                       <motion.div
                         className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                         initial={{ width: "0%" }}
                         animate={{ width: "100%" }}
                         transition={{ duration: 8, ease: "easeInOut" }}
                       />
                     </div>
                   </div>
                </motion.div>
              )}
              
              {(view === 'result' || view === 'error') && result && (
                <motion.div
                  key="result"
                  className="flex flex-col h-full space-y-6 overflow-y-auto p-1" // Added overflow-y-auto and padding
                  variants={fadeInUp}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                    {/* Analysis Section (Keep existing) */}
                    {result.analysis && (
                      <motion.div className="space-y-3" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <h3 className="flex items-center gap-2 font-semibold text-text-primary"><Bot size={20} className="text-accent-primary" /> AI Analysis</h3>
                        <div className="bg-background-light/50 p-4 rounded-lg border border-border-primary max-h-48 overflow-y-auto prose prose-invert prose-sm max-w-none">
                           <ReactMarkdown>{result.analysis}</ReactMarkdown>
                        </div>
                      </motion.div>
                    )}

                   {/* Code Output Section (Keep existing structure) */}
                   <div className="flex-grow flex flex-col min-h-0">
                      <div className="flex justify-between items-center mb-4">
                         <h3 className="text-lg font-semibold flex items-center gap-2">
                           {task === 'generate_tests' ? <FlaskConical size={20} /> : (task === 'generate_code' ? <Box size={20} /> : <Code size={20} />)} {/* Dynamic Icon */}
                           {task === 'generate_tests' ? 'Generated Tests' : (task === 'generate_code' ? 'Generated Code' : 'Corrected Code')} {/* Dynamic Title */}
                         </h3>
                         <motion.button onClick={() => copy()} className="btn btn-secondary flex items-center gap-2" whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                           {copyOK ? (<><ClipboardCheck size={16} className="text-green-400" /> {copyOK}</>) : (<><Clipboard size={16} /> Copy Code</>)}
                         </motion.button>
                      </div>
                      {typeof resultData === 'object' && Object.keys(resultData).length > 1 && ( /* Multi-file tabs */
                        <div className="flex gap-2 mb-3 border-b border-border-primary pb-2 flex-wrap"> {Object.keys(resultData).map(filename => (<button key={filename} onClick={() => setActiveFile(filename)} className={`btn btn-secondary text-xs px-3 py-1 ${activeFile === filename ? 'bg-accent-primary text-white border-accent-primary' : ''}`}>{filename}</button>))} </div>
                      )}
                      <div className="code-output-wrapper flex-grow rounded-lg bg-code-editor border border-border-primary p-4 overflow-auto">
                        <SyntaxHighlighter language={language} style={atomOneDark} wrapLines={true} wrapLongLines={true} customStyle={{ background: 'transparent', padding: 0, margin: 0, fontSize: '14px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }} useInlineStyles={true} PreTag="div" >
                           {activeFileContent || result.notice || "No code returned."}
                        </SyntaxHighlighter>
                      </div>
                    </div>
                     {/* --- END Code Output Section --- */}


                    {/* --- NEW: Sandbox Result Display (for generate_tests) --- */}
                    {result.sandbox_result && (
                       <motion.div className="space-y-3 pt-4 border-t border-border-secondary" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
                           <h3 className="flex items-center gap-2 font-semibold text-text-primary">
                               <FlaskConical size={20} className={result.sandbox_result.status === 'success' ? 'text-green-400' : 'text-red-400'} />
                               Sandbox Test Run
                               <Badge tone={result.sandbox_result.status === 'success' ? 'success' : 'error'}>
                                   Status: {result.sandbox_result.status || 'unknown'}
                               </Badge>
                           </h3>
                           {(result.sandbox_result.stdout || result.sandbox_result.stderr) && (
                               <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-60 overflow-y-auto bg-background-deep p-3 rounded border border-border-secondary"> {/* Added bg, padding, border */}
                                   {result.sandbox_result.stdout && (
                                       <div className="bg-background-light/50 p-3 rounded-lg border border-border-primary">
                                           <h4 className="text-xs font-semibold text-text-secondary mb-2">Stdout:</h4>
                                           <pre className="text-xs font-mono whitespace-pre-wrap break-all">{result.sandbox_result.stdout}</pre>
                                       </div>
                                   )}
                                   {result.sandbox_result.stderr && (
                                       <div className="bg-red-900/10 p-3 rounded-lg border border-red-500/20">
                                           <h4 className="text-xs font-semibold text-red-400 mb-2">Stderr:</h4>
                                           <pre className="text-xs font-mono whitespace-pre-wrap break-all text-red-300">{result.sandbox_result.stderr}</pre>
                                       </div>
                                   )}
                               </div>
                           )}
                           {result.sandbox_result.error && (
                               <p className="text-sm text-red-400">Sandbox Error: {result.sandbox_result.error}</p>
                           )}
                       </motion.div>
                    )}
                    {/* --- END Sandbox Result Display --- */}


                    {/* --- NEW: Validation Result Display (for generate_code) --- */}
                    {result.validation_result && !result.validation_result.error && (
                      <motion.div className="space-y-3 pt-4 border-t border-border-secondary" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                         <h3 className="flex items-center gap-2 font-semibold text-text-primary">
                             <Box size={20} className="text-purple-400" />
                             Code Validation
                         </h3>
                         <div className="flex gap-4 items-center bg-background-light/50 p-3 rounded-lg border border-border-primary">
                            <Badge tone={result.validation_result?.overall?.errors > 0 ? 'error' : (result.validation_result?.overall?.warnings > 0 ? 'warning' : 'success')}>
                                {result.validation_result?.overall?.errors > 0 ? 'Errors Found' : (result.validation_result?.overall?.warnings > 0 ? 'Warnings Found' : 'Validation Passed')}
                            </Badge>
                             <p className="text-sm text-text-secondary">
                                 Errors: <span className="font-semibold text-red-400">{result.validation_result?.overall?.errors || 0}</span>,
                                 Warnings: <span className="font-semibold text-yellow-400">{result.validation_result?.overall?.warnings || 0}</span>
                             </p>
                         </div>
                         {/* Display detailed findings */}
                         {Object.values(result.validation_result?.files || {}).some((file: any) => file.findings?.length > 0) && (
                            <details className="text-sm cursor-pointer mt-2">
                                <summary className="text-text-secondary hover:text-white transition-colors">Show detailed findings...</summary>
                                <div className="mt-2 space-y-4 max-h-60 overflow-y-auto bg-background-deep p-3 rounded border border-border-secondary">
                                    {Object.entries(result.validation_result?.files || {}).map(([path, fileResult]: [string, any]) => (
                                        fileResult.findings?.length > 0 && (
                                            <div key={path}>
                                                <p className="font-mono text-xs text-purple-300 mb-1">{path}</p>
                                                <ul className="list-disc pl-5 space-y-1">
                                                    {fileResult.findings.map((finding: any, idx: number) => (
                                                        <li key={idx} className={`text-xs flex items-start gap-2 ${finding.severity === 'error' ? 'text-red-300' : (finding.severity === 'warning' ? 'text-yellow-300' : 'text-gray-400')}`}>
                                                          <AlertCircle size={12} className={`mt-0.5 flex-shrink-0 ${finding.severity === 'error' ? 'text-red-500' : 'text-yellow-500'}`} />
                                                          <span>
                                                            <span className="font-semibold">[{finding.tool || 'validator'}]</span> Line {finding.line || 'N/A'}: {finding.message}
                                                          </span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )
                                    ))}
                                </div>
                            </details>
                         )}
                      </motion.div>
                    )}
                     {result.validation_result?.error && (
                       <motion.div className="pt-4 border-t border-border-secondary" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <p className="text-sm text-red-400 flex items-center gap-2"><AlertCircle size={16}/> Validation Error: {result.validation_result.error}</p>
                       </motion.div>
                     )}
                    {/* --- END Validation Result Display --- */}

                </motion.div>
              )}
               {/* --- END Result/Error View --- */}
            </AnimatePresence>
        </div>
      </aside>
    </main>
    </>
  );
}

export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [savedKeys, setSavedKeys] = useState<{ name: string; provider: string }[]>([]);
  const [userTier, setUserTier] = useState<string | null>(null);
  const [accountManagerView, setAccountManagerView] = useState('account');
  const [showLandingPage, setShowLandingPage] = useState(true);
  const [showPricingPage, setShowPricingPage] = useState(false);
  const [showAuthPage, setShowAuthPage] = useState(false);
  const [isUpgradeMode, setIsUpgradeMode] = useState(false);
  const [showQuotaModal, setShowQuotaModal] = useState(false);

  const handleEnterApp = () => setShowLandingPage(false);
  const handleNavigateToUpgrade = () => { setIsUpgradeMode(true); setPanelOpen(false); setShowPricingPage(true); };
  const handleGuestQuotaExceeded = () => setShowAuthPage(true);
  const handleUserQuotaExceeded = () => setShowQuotaModal(true);

  const getTierBadgeText = (tier: string | null): string => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      case 'developer': return 'Developer';
      case 'professional': return 'Professional';
      case 'enterprise': return 'Enterprise';
      default: return 'Free';
    }
  };

  const getBadgeClassName = (tier: string | null): string => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      case 'developer': return 'bg-orange-900/50 border-orange-500/50';
      case 'professional': return 'bg-blue-900/50 border-blue-500/50';
      case 'enterprise': return 'bg-emerald-900/50 border-emerald-500/50';
      default: return 'bg-gray-800/50 border-gray-600/50';
    }
  };

  const handleSelectPaidPlan = async (planId: string, billingCycle: "monthly" | "yearly") => {
  try {
    const response = await fetch(`${BACKEND_URL}/api/create-order`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      // CHANGE 1: Match the backend's expected field names (snake_case)
      body: JSON.stringify({
        plan_id: planId,
        billing_cycle: billingCycle
      }),
    });

    const orderData = await response.json();

    if (!response.ok) {
      throw new Error(orderData.detail || "Failed to create order.");
    }

    const options = {
      // CHANGE 2: Use the key sent from the backend
      key: orderData.razorpay_key_id,
      amount: orderData.amount,
      currency: orderData.currency,
      name: "0Pirate",
      description: `Subscription for ${planId} (${billingCycle})`,
      // CHANGE 3: Use the correct field 'order_id' from the backend response
      order_id: orderData.order_id,
      
      handler: function (_paymentResponse: any) {
  // The backend webhook at /api/razorpay-webhook will handle the upgrade.
  // We just close the UI and tell the user the upgrade is processing.
  
  setShowPricingPage(false);
  alert("Payment Successful! Your plan is now being upgraded.");

  if (user) {
    // We call loadUserProfile after a short delay to give the
    // backend webhook time to arrive and update the database.
    setTimeout(() => {
        loadUserProfile(user.id);
    }, 2500); // 2.5 second delay
  }
},
      
      prefill: {
        email: user?.email,
      },
      theme: {
        color: "#3B82F6",
      },
    };

    const paymentObject = new (window as any).Razorpay(options);
    paymentObject.open();

  } catch (error) {
    console.error("Payment failed:", error);
    alert("An error occurred during payment. Please check the console for details.");
  }
};

  const getBadgeFireGradient = (tier: string | null): string => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      case 'developer':
        return 'conic-gradient(from 90deg at 50% 50%, #FF7700 0%, #FFD700 50%, #FF7700 100%)';
      case 'professional':
        return 'conic-gradient(from 90deg at 50% 50%, #00C6FF 0%, #0072FF 50%, #00C6FF 100%)';
      case 'enterprise':
        return 'conic-gradient(from 90deg at 50% 50%, #69FF97 0%, #00E599 50%, #69FF97 100%)';
      default:
        return 'conic-gradient(from 90deg at 50% 50%, #FFFFFF 0%, #999999 50%, #FFFFFF 100%)';
    }
  };

  const loadKeys = useCallback(async () => {
    if (!token) { setSavedKeys([]); return; }
    try {
      const res = await fetch(`${BACKEND_URL}/api/keys`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error("Could not fetch keys");
      const data = await res.json();
      setSavedKeys(data.keys || []);
    } catch (e) { console.error("Failed to load keys:", e); setSavedKeys([]); }
  }, [token]);

  
  const loadUserProfile = useCallback(async (userId: string) => {
    if (!userId) return;
    try {
      const { data, error } = await supabase.from('profiles').select('tier').eq('id', userId).single();
      if (error) { throw error; }
      if (data) { setUserTier(data.tier || "free"); }
    } catch (e: any) { 
      // --- THIS IS THE FIX ---
      // Use String(e.message || e) to avoid the "[object Object]" or "{}" logs
      console.error("Failed to load user profile:", String(e.message || e)); 
      setUserTier("free"); 
    }
  }, []);

  useEffect(() => { if (token) { loadKeys(); } }, [token, loadKeys]);
   useEffect(() => {
    const handleAuthChange = async (session: any) => {
      setUser(session?.user ?? null);
      setToken(session?.access_token ?? null);
      if (session?.user) { 
        await loadUserProfile(session.user.id); 
        setShowLandingPage(false); // <-- ADD THIS LINE
      } else { 
        setUserTier(null); 
      }
    };
    supabase.auth.getSession().then(({ data: { session } }) => { handleAuthChange(session); });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => { handleAuthChange(session); });
    return () => { subscription?.unsubscribe(); };
  }, [loadUserProfile]);
  
  return (
    <div className="min-h-screen flex flex-col bg-background-deep relative">
      <Script
        id="razorpay-checkout-js"
        src="https://checkout.razorpay.com/v1/checkout.js"
      />
      <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2" async defer></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js" async defer></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js" async defer></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js" async defer></script>
      <InteractiveBackground />
      <style>{`
        body::before {
          content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: radial-gradient( circle 600px at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(74, 144, 226, 0.1), transparent 80% );
          pointer-events: none; z-index: -1;
        }
      `}</style>
      
      

{showLandingPage ? (
    // 1. If true, show ONLY the LandingPage
    <LandingPage onNavigate={handleEnterApp} />
) : (
    // 2. If false, show the complete app UI (Header + MainApp)
    <>
        <header className="main-container app-header py-6 flex justify-between items-center">
    <div className="flex items-center gap-4">
        {/* Logo and tagline */}
        <motion.div 
            initial={{ opacity: 0, x: -20 }} 
            animate={{ opacity: 1, x: 0 }} 
            transition={{ duration: 0.6 }} 
            className="flex flex-col"
        >
            <h1 className="app-title bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                0Pirate
            </h1>
            <p className="app-tagline -mt-1">Secure & Refactor Your Code with AI</p>
        </motion.div>

        {/* Enhanced Tier Badge - Properly centered */}
        <AnimatePresence>
            {user && userTier && (
                <motion.div
                    key={userTier}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.3 }}
                    className={`tier-badge ${getBadgeClassName(userTier)}`}
                    style={{ alignSelf: 'center' }}
                >
                    {/* Tier text */}
                    <span className="relative z-20 drop-shadow-lg">
                        {getTierBadgeText(userTier)}
                    </span>
                    
                    {/* Animated rotating gradient background */}
                    <div className="absolute inset-0 z-0 overflow-hidden rounded-full">
                        <motion.div
                            className="absolute top-1/2 left-1/2 w-[200%] h-[200%] -translate-x-1/2 -translate-y-1/2 opacity-50"
                            style={{ background: getBadgeFireGradient(userTier) }}
                            animate={{ rotate: 360 }}
                            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                        />
                    </div>
                    
                    {/* Shimmer effect */}
                    <div className="absolute inset-0 z-10 overflow-hidden rounded-full">
                        <motion.div
                            className="absolute inset-0 w-full h-full"
                            style={{
                                background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
                            }}
                            animate={{ x: ['-100%', '200%'] }}
                            transition={{ duration: 2, repeat: Infinity, ease: "linear", repeatDelay: 1 }}
                        />
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    </div>

    {/* User actions on the right */}
    {user ? (
        <div className="flex items-center gap-3">
            <motion.button 
                onClick={() => { setAccountManagerView('api_keys'); setPanelOpen(true); }} 
                className="btn bg-emerald-500/20 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 group"
                initial={{ opacity: 0, x: 20 }} 
                animate={{ opacity: 1, x: 0 }} 
                transition={{ duration: 0.6, delay: 0.3 }}
                whileHover={{ scale: 1.05 }} 
                whileTap={{ scale: 0.95 }}
            >
                <KeyRound size={16} /> Add API Key
            </motion.button>
            <motion.button 
                onClick={() => { setAccountManagerView('account'); setPanelOpen(true); }} 
                className="btn btn-secondary group"
                initial={{ opacity: 0, x: 20 }} 
                animate={{ opacity: 1, x: 0 }} 
                transition={{ duration: 0.6, delay: 0.2 }}
                whileHover={{ scale: 1.05 }} 
                whileTap={{ scale: 0.95 }}
            >
                <User size={16} className="group-hover:scale-110 transition-transform" /> Account
            </motion.button>
        </div>
    ) : (
        <motion.button 
            onClick={() => setShowAuthPage(true)} 
            className="btn btn-primary group" 
            initial={{ opacity: 0, x: 20 }} 
            animate={{ opacity: 1, x: 0 }} 
            transition={{ duration: 0.6, delay: 0.2 }} 
            whileHover={{ scale: 1.05 }} 
            whileTap={{ scale: 0.95 }}
        >
            Sign Up / Log In
        </motion.button>
    )}
</header>


        <div className="main-container flex-grow flex flex-col">
            <MainApp
                token={token}
                savedKeys={savedKeys}
                onGuestQuotaExceeded={handleGuestQuotaExceeded}
                onUserQuotaExceeded={handleUserQuotaExceeded}
            />
        </div>
    </>
)}

      <AnimatePresence>
        {panelOpen && (
          <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setPanelOpen(false)}>
            <div onClick={(e) => e.stopPropagation()}>
              <AccountManager 
                token={token} 
                email={user?.email} 
                savedKeys={savedKeys} 
                onKeysChange={loadKeys} 
                userTier={userTier} 
                onClose={() => setPanelOpen(false)} 
                onUpgrade={handleNavigateToUpgrade}
                activeView={accountManagerView}
                setActiveView={setAccountManagerView}
              />
            </div>
          </motion.div>
        )}

        {/* ADD THIS BLOCK FOR THE NEW MODAL */}
    {showQuotaModal && (
      <QuotaExceededModal
        isOpen={showQuotaModal}
        userTier={getTierBadgeText(userTier)}
        onClose={() => setShowQuotaModal(false)}
        onUpgrade={() => {
          setShowQuotaModal(false);
          handleNavigateToUpgrade();
        }}
      />
    )}

        {showPricingPage && (
       <motion.div key="pricing" className="modal-backdrop" {...scaleIn}>
          <PricingPage 
            onClose={() => setShowPricingPage(false)}
            onSelectFreePlan={() => setShowPricingPage(false)} 
            onSelectPaidPlan={handleSelectPaidPlan} 
            isUpgradeMode={isUpgradeMode} 
          />
       </motion.div>
    )}
        {showAuthPage && (
          <motion.div key="auth" className="modal-backdrop" {...scaleIn}>
            <AuthComponent onAuthSuccess={() => setShowAuthPage(false)} />
          </motion.div>
        )}


      </AnimatePresence>
    </div>
  );
}