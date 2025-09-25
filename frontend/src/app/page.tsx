"use client";

import React, { useState, useEffect, useCallback, Fragment, useRef } from "react";
import { createClient } from "@supabase/supabase-js";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion";

import {
  User, Bot, Terminal, Clipboard, ClipboardCheck, LogOut, Github, Mail, KeyRound,
  Trash2, X, ShieldCheck, FileText, Zap, HelpCircle, Code, Settings, Edit, ChevronLeft, Loader2, ArrowRight, MessageSquare, Linkedin
} from "lucide-react";

import LandingPage from "./landing_page";
import PricingPage from "./pricing";
import Script from 'next/script';

import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";


/* --- Interactive Components --- */

// This component tracks the mouse and applies a spotlight effect to the background.
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

// This is the bot icon that follows the cursor with a 3D tilt effect.
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
    <motion.div
      ref={ref}
      style={{
        transformStyle: "preserve-3d",
        rotateX,
        rotateY,
      }}
      className="mb-6 lp-hero-icon"
    >
      <div style={{ transform: "translateZ(20px)" }}>
        <Bot size={40} />
      </div>
    </motion.div>
  );
}

// --- Animation Variants ---
const fadeInUp = {
  initial: { opacity: 0, y: 50 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.8, ease: "easeOut" } }
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.1 } }
};

const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 }
};



/* -------------------------------------------------
   Configuration
---------------------------------------------------*/
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

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
type ResultShape = { result?: Record<string, string> | string; analysis?: string; notice?: string; job_id?: string; };


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
            setStatus(`${steps[stepIndex++ % steps.length]}`);
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
   Small Components
---------------------------------------------------*/
const Badge = ({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) => { 
    const cls = tone === "success" 
        ? "inline-flex items-center px-3 py-1 rounded-full bg-emerald-600/20 border border-emerald-600/30 text-emerald-300 text-xs font-medium" 
        : tone === "warn" 
        ? "inline-flex items-center px-3 py-1 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-medium" 
        : tone === "info" 
        ? "inline-flex items-center px-3 py-1 rounded-full bg-blue-600/20 border border-blue-600/30 text-blue-300 text-xs font-medium" 
        : "inline-flex items-center px-3 py-1 rounded-full bg-gray-500/20 border border-gray-500/30 text-gray-300 text-xs font-medium"; 
    return <span className={cls}>{children}</span>; 
};

/* -------------------------------------------------
   Enhanced Loading Spinner
---------------------------------------------------*/
const LoadingSpinner = ({ size = 20, className = "" }: { size?: number; className?: string }) => (
  <motion.div
    className={`inline-block ${className}`}
    animate={{ rotate: 360 }}
    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
  >
    <Loader2 size={size} />
  </motion.div>
);



/* -------------------------------------------------
   Redesigned Auth Component
---------------------------------------------------*/
const AuthComponent = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isPasswordFocused, setIsPasswordFocused] = useState(false); // State for password focus

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const authMethod = isSignUp ? supabase.auth.signUp : supabase.auth.signInWithPassword;
      const { error } = await authMethod({ email, password });
      if (error) setError(error.message);
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
        transition={{ duration: 0.6 }}
      >
        <div className="flex justify-center mb-6">
          <InteractiveBotIcon isPasswordActive={isPasswordFocused} />
        </div>
        <h1 className="flex items-center justify-center gap-3 text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          0Pirate
        </h1>
        <p className="text-text-secondary mt-3 text-lg">
          {isSignUp ? "Create your account to get started" : "Welcome back to the future of code"}
        </p>
      </motion.div>
      
      <motion.div 
        className="card auth-card"
        variants={scaleIn}
        initial="initial"
        animate="animate"
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <motion.div 
          className="auth-social-buttons"
          variants={staggerContainer}
          initial="initial"
          animate="animate"
        >
          <motion.button 
            onClick={() => oauth("github")} 
            className="btn btn-secondary auth-social-button group"
            variants={fadeInUp}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Github size={18} className="group-hover:scale-110 transition-transform" /> 
            Continue with GitHub
          </motion.button>
          <motion.button 
            onClick={() => oauth("google")} 
            className="btn btn-secondary auth-social-button group"
            variants={fadeInUp}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Mail size={18} className="group-hover:scale-110 transition-transform" /> 
            Continue with Google
          </motion.button>
        </motion.div>
        
        <div className="auth-divider">or continue with email</div>
        
        <form onSubmit={handleAuth} className="flex flex-col gap-4">
          <motion.input 
            className="input-base focus:ring-2 focus:ring-blue-500/30 transition-all" 
            type="email" 
            placeholder="Enter your email address" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)} 
            required 
            variants={fadeInUp}
            initial="initial"
            animate="animate"
          />
          <motion.input 
            className="input-base focus:ring-2 focus:ring-blue-500/30 transition-all" 
            type="password" 
            placeholder="Enter your password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            required 
            variants={fadeInUp}
            initial="initial"
            animate="animate"
            onFocus={() => setIsPasswordFocused(true)}
            onBlur={() => setIsPasswordFocused(false)}
          />
          <motion.button 
            type="submit" 
            disabled={loading} 
            className="btn btn-primary w-full relative overflow-hidden"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            variants={fadeInUp}
            initial="initial"
            animate="animate"
          >
            {loading ? (
              <div className="flex items-center justify-center gap-2">
                <LoadingSpinner size={16} />
                Processing...
              </div>
            ) : (
              isSignUp ? "Create Account" : "Sign In"
            )}
          </motion.button>
        </form>
        
        <AnimatePresence>
          {error && (
            <motion.div
              className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <p className="text-red-400 text-sm text-center">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>
        
        <p className="text-center text-sm text-text-secondary mt-6">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}
          <motion.button 
            onClick={() => setIsSignUp(!isSignUp)} 
            className="btn btn-link text-accent-primary hover:text-accent-primary-hover ml-2 px-0 py-0 h-auto font-medium"
            whileHover={{ scale: 1.05 }}
          >
            {isSignUp ? "Sign In" : "Sign Up"}
          </motion.button>
        </p>
      </motion.div>
    </div>
  );
};

/* -------------------------------------------------
   Enhanced Claude-style Onboarding View
---------------------------------------------------*/
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
      {/* The static Bot icon is now replaced with the interactive one */}
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

/* -------------------------------------------------
   Enhanced Confirmation Modal
---------------------------------------------------*/
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

/* -------------------------------------------------
   Enhanced API Keys View
---------------------------------------------------*/
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
            {/* Form Section */}
            <motion.div 
                className="space-y-6"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
            >
                <div className="flex items-center gap-3">
                    <KeyRound size={24} className="text-accent-primary" />
                    <h3 className="text-2xl font-semibold">
                        {editingKeyName ? `Edit '${editingKeyName}'` : "Add New API Key"}
                    </h3>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-text-secondary">Key Name (Optional)</label>
                        <input 
                            className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                            type="text" 
                            placeholder="e.g., Personal Gemini Key" 
                            value={keyName} 
                            onChange={(e) => setKeyName(e.target.value)} 
                            disabled={!!editingKeyName} 
                        />
                    </div>
                    
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-text-secondary">Provider</label>
                        <select 
                            className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                            value={provider} 
                            onChange={(e) => setProvider(e.target.value)} 
                            disabled={!!editingKeyName}
                        >
                            {Object.keys(MODEL_OPTIONS).filter((p) => !["auto", "ollama"].includes(p)).map((p) => 
                                <option key={p} value={p} className="capitalize">{p}</option>
                            )}
                        </select>
                    </div>
                </div>
                
                <div className="space-y-2">
                    <label className="text-sm font-medium text-text-secondary">API Key</label>
                    <input 
                        className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                        type="password" 
                        placeholder={editingKeyName ? "Enter new key to update" : "Paste your API key here"} 
                        value={apiKey} 
                        onChange={(e) => setApiKey(e.target.value)} 
                    />
                </div>
                
                <div className="flex gap-3 pt-2">
                    {editingKeyName && (
                        <motion.button 
                            onClick={resetForm} 
                            className="btn btn-secondary flex-1"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            Cancel Edit
                        </motion.button>
                    )}
                    <motion.button 
                        onClick={saveOrUpdateKey} 
                        disabled={isLoading}
                        className="btn btn-primary flex-1"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        {isLoading ? (
                            <div className="flex items-center gap-2">
                                <LoadingSpinner size={14} />
                                Saving...
                            </div>
                        ) : (
                            editingKeyName ? "Update Key" : "Save Key"
                        )}
                    </motion.button>
                </div>
                
                <AnimatePresence>
                    {message && (
                        <motion.div
                            className={`text-center p-3 rounded-lg border ${
                                message.startsWith('✓') 
                                    ? 'bg-green-500/10 border-green-500/20 text-green-400' 
                                    : 'bg-red-500/10 border-red-500/20 text-red-400'
                            }`}
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                        >
                            <p className="text-sm">{message}</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* Saved Keys Section */}
            <motion.div 
                className="space-y-6"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                transition={{ delay: 0.1 }}
            >
                <div className="flex items-center gap-3">
                    <Settings size={24} className="text-accent-primary" />
                    <h3 className="text-2xl font-semibold">Saved Keys</h3>
                    {savedKeys.length > 0 && (
                        <Badge tone="info">{savedKeys.length} keys</Badge>
                    )}
                </div>
                
                {savedKeys.length > 0 ? (
                    <div className="space-y-3">
                        {savedKeys.map((key, index) => (
                            <motion.div 
                                key={key.name} 
                                className="settings-row bg-background-light/30 p-4 rounded-xl border border-border-primary hover:border-accent-primary/30 transition-all duration-200"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.05 }}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-2 h-2 bg-accent-primary rounded-full"></div>
                                    <div>
                                        <p className="font-mono text-sm font-medium text-text-primary">{key.name}</p>
                                        <p className="text-xs text-text-secondary capitalize">Provider: {key.provider}</p>
                                    </div>
                                </div>
                                
                                <div className="flex gap-2">
                                    <motion.button 
                                        onClick={() => handleEditClick(key)} 
                                        className="btn btn-secondary text-sm px-3 py-1.5"
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                    >
                                        <Edit size={14}/> Edit
                                    </motion.button>
                                    <motion.button 
                                        onClick={() => handleDeleteClick(key.name)} 
                                        className="btn btn-destructive text-sm px-3 py-1.5"
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                    >
                                        <Trash2 size={14}/> Delete
                                    </motion.button>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                ) : (
                    <motion.div 
                        className="text-center py-12 px-6 border border-dashed border-border-primary rounded-xl"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    >
                        <KeyRound size={48} className="mx-auto text-text-secondary mb-4" />
                        <p className="text-text-secondary text-lg mb-2">No API keys saved yet</p>
                        <p className="text-text-secondary/70 text-sm">Add your first API key to get started with AI-powered code analysis</p>
                    </motion.div>
                )}
            </motion.div>
            
            <ConfirmationModal
                isOpen={isConfirmModalOpen}
                onClose={() => setConfirmModalOpen(false)}
                onConfirm={handleConfirmDelete}
                title="Delete API Key"
                promptText={keyToDelete || ""}
                confirmLabel="Delete Key"
            >
                <p>This action cannot be undone. This will permanently delete the <strong className="text-red-400">{keyToDelete}</strong> API key from your account.</p>
            </ConfirmationModal>
        </div>
    );
}

/* -------------------------------------------------
   Enhanced Account Manager
---------------------------------------------------*/
function AccountManager({ token, email, savedKeys, onKeysChange, onClose, userTier, onUpgrade }: {
  token: string | null;
  email: string | undefined;
  savedKeys: { name: string; provider: string }[];
  onKeysChange: () => void;
  onClose: () => void;
  userTier: string | null;
  onUpgrade: () => void; // Accept the new onUpgrade prop
}) {
  const [activeView, setActiveView] = useState('account');
  
  const getTierBadgeProps = (tier: string | null) => {
    const tierLower = tier?.toLowerCase();
    switch (tierLower) {
      // FIX: Changed 'pro' to 'developer' to match your plans
      case 'developer': return { tone: 'info', children: 'Developer Plan' };
      case 'professional': return { tone: 'info', children: 'Professional Plan' };
      case 'enterprise': return { tone: 'success', children: 'Enterprise' };
      default: return { tone: 'default', children: 'Free Plan' };
    }
  };

  const navItems = [
    { id: 'account', label: 'Account', icon: User },
    { id: 'api_keys', label: 'API Keys', icon: KeyRound }
  ];

  return (
    <motion.div 
      className="modal-panel"
      variants={scaleIn}
      initial="initial"
      animate="animate"
      exit="exit"
    >
        <div className="settings-header">
            <motion.button 
                onClick={onClose} 
                className="btn btn-secondary"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
            >
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
                            exit="exit"
                            className="space-y-8"
                        >
                            <motion.div className="settings-section">
                                <h3 className="flex items-center gap-3">
                                    <User size={24} className="text-accent-primary" />
                                    Account Information
                                </h3>
                                <div className="settings-row bg-background-light/30 p-4 rounded-xl border border-border-primary">
                                    <div className="settings-row-info">
                                        <label>Email Address</label>
                                        <p className="text-text-primary font-mono">{email}</p>
                                    </div>
                                    <motion.button 
                                        className="btn btn-secondary text-sm"
                                        whileHover={{ scale: 1.05 }}
                                    >
                                        Change Email
                                    </motion.button>
                                </div>
                            </motion.div>
                            
                            <motion.div className="settings-section">
                                <h3 className="flex items-center gap-3">
                                    <Zap size={24} className="text-accent-primary" />
                                    Subscription
                                </h3>
                                <div className="settings-row bg-background-light/30 p-4 rounded-xl border border-border-primary">
                                    <div className="settings-row-info">
                                        <label>Current Plan</label>
                                        <div className="mt-2">
                                            <Badge {...getTierBadgeProps(userTier)}/>
                                        </div>
                                    </div>
                                    {/* FIXED: This button now correctly triggers the upgrade flow */}
                                    <motion.button 
                                        onClick={onUpgrade} 
                                        className="btn btn-primary"
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                    >
                                        Upgrade Plan
                                    </motion.button>
                                </div>
                            </motion.div>
                            
                            <motion.div className="settings-section">
                                <h3 className="flex items-center gap-3">
                                    <LogOut size={24} className="text-accent-primary" />
                                    Account Actions
                                </h3>
                                <div className="settings-row bg-background-light/30 p-4 rounded-xl border border-border-primary">
                                    <div className="settings-row-info">
                                        <label>Sign Out</label>
                                        <p className="text-text-secondary">End your current session securely</p>
                                    </div>
                                    <motion.button 
                                        onClick={() => supabase.auth.signOut()} 
                                        className="btn btn-secondary"
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                    >
                                        <LogOut size={16} />
                                        Sign Out
                                    </motion.button>
                                </div>
                            </motion.div>
                        </motion.div>
                    )}
                    
                    {activeView === 'api_keys' && (
                        <motion.div
                            key="api_keys"
                            variants={fadeInUp}
                            initial="initial"
                            animate="animate"
                            exit="exit"
                        >
                            <ApiKeysView token={token} savedKeys={savedKeys} onKeysChange={onKeysChange} />
                        </motion.div>
                    )}
                </AnimatePresence>
            </main>
        </div>
    </motion.div>
  );
}

/* -------------------------------------------------
   FINAL PROFESSIONAL TOGGLE SWITCH COMPONENT
---------------------------------------------------*/
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
      style={{ borderColor: checked ? activeColor : 'var(--border-primary)' }} // Dynamically set border color
    >
      <div className="flex justify-between items-start">
        <div className="toggle-switch-info flex-grow">
          {/* FIXED: The title color now correctly turns green when active */}
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
            // FIXED: The slider's background color now correctly turns green when active
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
            {/* FIXED: The "active info" text now correctly turns green */}
            <p className="toggle-active-info" style={{ color: activeColor }}>
              {Icon && <Icon size={16} />} {activeInfo}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* -------------------------------------------------
   Enhanced Main Application Component
---------------------------------------------------*/
function MainApp({ token, savedKeys }: { token: string | null; savedKeys: { name: string; provider: string }[] }) {
  type ViewState = JobStatus;
  const [pastedCode, setPastedCode] = useState("");
  const [errorLog, setErrorLog] = useState("");
  const [task, setTask] = useState("fix_and_secure");
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

  const [inputMode, setInputMode] = useState<'paste' | 'upload'>('paste');
  const [files, setFiles] = useState<File[]>([]);

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
    let resultData = d.result || {};
    let firstFileName = null;
    if (typeof resultData === 'string') {
      try { resultData = JSON.parse(resultData); } 
      catch (e) {
        console.error("Failed to parse result JSON:", e);
        setResult({ ...d, result: { notice: resultData } });
        setView("result");
        return;
      }
    }
    if (typeof resultData === 'object' && Object.keys(resultData).length > 0) {
      firstFileName = Object.keys(resultData)[0];
    }
    setResult({ ...d, result: resultData });
    setActiveFile(firstFileName);
    setView("result");
    setStatus("Analysis completed successfully");
  }, []);

  const fail = useCallback((err: string) => { 
    if (err?.includes?.("Daily job quota")) { 
      setView("upgrade"); 
    } else { 
      setResult({ notice: `Error: ${err}` }); 
      setView("error"); 
    } 
    setStatus("Analysis failed"); 
  }, []);
  
  useJobPolling(jobId, token, success, fail, setStatus);

  useEffect(() => {
    if (savedKeys) {
      const keysForProvider = savedKeys.filter(k => k.provider === provider);
      setSelectedKeyName(keysForProvider.length > 0 ? keysForProvider[0].name : "");
    }
  }, [provider, savedKeys]);
  
  const submit = async () => {
    if (!pastedCode.trim()) return fail("Please paste your code.");
    const requiresKey = !['auto', 'ollama'].includes(provider);
    if (requiresKey && !selectedKeyName) { 
      return fail(`Please save an API key for '${provider}' in your account.`); 
    }
    
    setView("loading");
    setResult(null);
    setJobId(null);
    setStatus("Submitting analysis request...");
    
    const fd = new FormData();
    fd.append("files", new Blob([pastedCode]), "pasted_code.py");
    fd.append("task", task);
    if (errorLog) fd.append("error_log", errorLog);
    fd.append("provider", provider);
    if (model) fd.append("model", model);
    if (selectedKeyName) fd.append("api_key_name", selectedKeyName);
    fd.append("token_saver_enabled", String(tokenSaver));
    fd.append("abstraction_enabled", String(maxSecurity));
    fd.append("abstraction_level", maxSecurity ? "paranoid" : "standard");
    
    try {
      if (!token) throw new Error("Authentication token is missing.");
      const res = await fetch(`${BACKEND_URL}/api/process_code`, { 
        method: "POST", 
        headers: { Authorization: `Bearer ${token}` }, 
        body: fd 
      });
      const d = await res.json();
      if (res.ok) { 
        setJobId(d.job_id); 
        setStatus("Job submitted, processing..."); 
      } else { 
        fail(d.detail || "Submission failed."); 
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
  };

  useEffect(() => { 
    const models = MODEL_OPTIONS[provider] || ["(auto-select)"]; 
    setModel(models[0]); 
  }, [provider]);
  
  const resultData = result?.result || {};
  const activeFileContent = activeFile && typeof resultData === "object" ? (resultData as Record<string, string>)[activeFile] : (typeof resultData === "string" ? resultData : "");

  const taskOptions = [
    { value: "fix_and_secure", label: "Fix & Secure", icon: Zap },
    { value: "code_review", label: "Code Review", icon: HelpCircle },
    { value: "documentation", label: "Add Documentation", icon: FileText },
    { value: "refactor", label: "Refactor", icon: Code },
    { value: "explain", label: "Explain Code", icon: Terminal }
  ];

  return (
    <main className="content-grid">
      {/* FIXED: The left pane is now a flex column to make buttons sticky */}
      <div className="left-pane flex flex-col gap-6">
        
        {/* This new wrapper contains all the scrollable content */}
        <div className="flex-grow space-y-6 overflow-y-auto pr-2">
          <motion.div 
            className="space-y-6"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            {/* Code Input Section */}
            <motion.div variants={fadeInUp}>
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

                <div className="code-wrapper group lg:col-start-2">
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
            </motion.div>

            {/* Task Selection */}
            <motion.div className="card space-y-6" variants={fadeInUp}>
              <div className="space-y-3">
                <label className="text-sm font-medium text-text-secondary flex items-center gap-2">
                  <Settings size={16} />
                  Task Selection
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
                <div className="space-y-2">
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
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-secondary">Model</label>
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
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-secondary">API Key</label>
                  <select 
                    className="input-base transition-all duration-200 focus:ring-2 focus:ring-blue-500/30" 
                    value={selectedKeyName} 
                    onChange={(e) => setSelectedKeyName(e.target.value)} 
                    disabled={savedKeys.filter(k => k.provider === provider).length === 0}
                  >
                    {savedKeys.filter(k => k.provider === provider).length === 0 ? 
                      (<option value="">No keys saved for {provider}</option>) : 
                      (savedKeys.filter(key => key.provider === provider).map((key) => (
                        <option key={key.name} value={key.name}>{key.name}</option>
                      )))
                    }
                  </select>
                </div>
              )}
            </motion.div>

            {/* Settings Toggles */}
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
            </motion.div>
          </motion.div>
        </div>
        
        {/* The action buttons are now outside the scrolling container, making them 'sticky' */}
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
                   <motion.div
                     animate={{ rotate: 360 }}
                     transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                   >
                     <Bot size={48} className="text-accent-primary" />
                   </motion.div>
                   
                   <div className="space-y-2">
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
                  className="flex flex-col h-full space-y-6"
                  variants={fadeInUp}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                    {result.analysis && (
                      <motion.div 
                        className="space-y-3"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <h3 className="flex items-center gap-2 font-semibold text-text-primary">
                          <Bot size={20} className="text-accent-primary" /> 
                          AI Analysis
                        </h3>
                        <div className="bg-background-light/50 p-4 rounded-lg border border-border-primary max-h-48 overflow-y-auto">
                          <pre className="whitespace-pre-wrap text-sm text-text-secondary leading-relaxed font-sans">
                            {result.analysis}
                          </pre>
                        </div>
                      </motion.div>
                    )}
                    
                    <div className="flex-grow flex flex-col min-h-0">
                      <div className="flex justify-between items-center mb-4">
                         <h3 className="text-lg font-semibold flex items-center gap-2">
                           <Code size={20} />
                           Corrected Code
                         </h3>
                         <motion.button 
                           onClick={() => copy()} 
                           className="btn btn-secondary flex items-center gap-2"
                           whileHover={{ scale: 1.05 }}
                           whileTap={{ scale: 0.95 }}
                         >
                           {copyOK ? (
                             <>
                               <ClipboardCheck size={16} className="text-green-400" />
                               {copyOK}
                             </>
                           ) : (
                             <>
                               <Clipboard size={16} />
                               Copy Code
                             </>
                           )}
                         </motion.button>
                      </div>

                      {typeof resultData === 'object' && Object.keys(resultData).length > 1 && (
                        <div className="flex gap-2 mb-3 border-b border-border-primary pb-2 flex-wrap">
                          {Object.keys(resultData).map(filename => (
                            <button
                              key={filename}
                              onClick={() => setActiveFile(filename)}
                              className={`btn btn-secondary text-xs px-3 py-1 ${activeFile === filename ? 'bg-accent-primary text-white border-accent-primary' : ''}`}
                            >
                              {filename}
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="code-output-wrapper flex-grow rounded-lg bg-code-editor border border-border-primary p-4 overflow-auto">
                        <SyntaxHighlighter 
                          language={language}
                          style={atomOneDark} 
                          wrapLines={true} 
                          wrapLongLines={true}
                          customStyle={{ background: 'transparent', padding: 0, margin: 0, fontSize: '14px' }}
                        >
                          {activeFileContent || result.notice || "No code returned."}
                        </SyntaxHighlighter>
                      </div>
                    </div>
                </motion.div>
              )}
            </AnimatePresence>
        </div>
      </aside>
    </main>
  );
}
/*-------------------------------------------------
   Top-level Home wrapper
---------------------------------------------------*/
export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [savedKeys, setSavedKeys] = useState<{ name: string; provider: string }[]>([]);
  const [userTier, setUserTier] = useState<string | null>(null);
  
  const [currentView, setCurrentView] = useState<'landing' | 'pricing' | 'auth'>('landing');

  // --- ADDED STATE to manage the upgrade flow ---
  const [isUpgradeMode, setIsUpgradeMode] = useState(false);


  // Navigate from Landing to Pricing
  const handleNavigateToPricing = () => {
    setIsUpgradeMode(false); // This is NOT an upgrade flow
    setCurrentView('pricing');
  };

  // --- ADDED HANDLER for the upgrade button in AccountManager ---
  const handleNavigateToUpgrade = () => {
    setIsUpgradeMode(true); // This IS an upgrade flow
    setPanelOpen(false); // Close the account panel
    setCurrentView('pricing'); // Switch view to pricing page
  };


  // On the pricing page, if the user selects the Free plan, navigate to auth
  const handleSelectFreePlan = () => {
    setIsUpgradeMode(false);
    setCurrentView('auth');
  };

  // On the pricing page, if the user selects a Paid plan, start the payment flow
  const handleSelectPaidPlan = async (planId: string, billingCycle: 'monthly' | 'yearly') => {
    if (!token || !user) {
      alert("Please sign up or log in to choose a plan.");
      setCurrentView('auth');
      return;
    }

    try {
      const orderResponse = await fetch(`${BACKEND_URL}/api/create-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle })
      });

      if (!orderResponse.ok) {
        throw new Error("Failed to create payment order.");
      }

      const orderDetails = await orderResponse.json();

      const options = {
        key: orderDetails.razorpay_key_id,
        amount: orderDetails.amount,
        currency: orderDetails.currency,
        name: "0Pirate",
        description: `Payment for ${planId} plan (${billingCycle})`,
        order_id: orderDetails.order_id,
        handler: function (response: any) {
          alert("Payment successful! Your plan has been upgraded. Please refresh if you don't see the change.");
          // Refresh user profile to get new tier
          if (user) loadUserProfile(user.id);
        },
        prefill: {
          email: user.email,
        },
        theme: {
          color: "#3B82F6"
        }
      };
      
      const rzp = new (window as any).Razorpay(options);
      rzp.open();

    } catch (err) {
      console.error("Payment flow failed:", err);
      alert("An error occurred during the payment process. Please try again.");
    }
  };
  
  const loadKeys = useCallback(async () => {
    if (!token) { setSavedKeys([]); return; }
    try {
      const res = await fetch(`${BACKEND_URL}/api/keys`, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      if (!res.ok) throw new Error("Could not fetch keys");
      const data = await res.json();
      setSavedKeys(data.keys || []);
    } catch (e) { 
      console.error("Failed to load keys:", e); 
      setSavedKeys([]); 
    }
  }, [token]);

  const loadUserProfile = useCallback(async (userId: string) => {
    if (!userId) return;
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('tier')
        .eq('id', userId)
        .single();
      if (error) { throw error; }
      if (data) { setUserTier(data.tier || "free"); }
    } catch (e) { 
      console.error("Failed to load user profile:", e); 
      setUserTier("free"); 
    }
  }, []);

  useEffect(() => {
    if (token) { loadKeys(); }
  }, [token, loadKeys]);

  useEffect(() => {
    const handleAuthChange = async (session: any) => {
      setUser(session?.user ?? null);
      setToken(session?.access_token ?? null);
      if (session?.user) { 
        await loadUserProfile(session.user.id); 
      } else { 
        setUserTier(null); 
        setCurrentView('landing');
      }
    };
    
    supabase.auth.getSession().then(({ data: { session } }) => { 
      handleAuthChange(session); 
    });
    
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => { 
      handleAuthChange(session); 
    });
    
    return () => { subscription?.unsubscribe(); };
  }, [loadUserProfile]);
  
  const renderView = () => {
    if (user && currentView !== 'pricing') { // Ensure pricing page can be shown when logged in
      return (
        <Fragment>
          <AnimatePresence>
            {panelOpen && (
              <motion.div 
                className="modal-backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setPanelOpen(false)}
              >
                <div onClick={(e) => e.stopPropagation()}>
                  <AccountManager 
                    token={token} 
                    email={user?.email} 
                    savedKeys={savedKeys} 
                    onKeysChange={loadKeys}
                    userTier={userTier}
                    onClose={() => setPanelOpen(false)}
                    onUpgrade={handleNavigateToUpgrade} // Pass the new handler
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <MainApp token={token} savedKeys={savedKeys} />
        </Fragment>
      );
    }

    switch (currentView) {
      case 'landing':
        return <LandingPage onNavigate={handleNavigateToPricing} />;
      case 'pricing':
        return <PricingPage 
                  onSelectFreePlan={handleSelectFreePlan} 
                  onSelectPaidPlan={handleSelectPaidPlan} 
                  isUpgradeMode={isUpgradeMode} // Pass the state as a prop
               />;
      case 'auth':
        return <AuthComponent />;
      default:
        return <LandingPage onNavigate={handleNavigateToPricing} />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-background-deep relative">
      <InteractiveBackground />
      <style>{`
        body::before {
          content: '';
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: radial-gradient(
            circle 600px at var(--mouse-x, 50%) var(--mouse-y, 50%),
            rgba(74, 144, 226, 0.1),
            transparent 80%
          );
          pointer-events: none;
          z-index: -1;
        }
      `}</style>
     
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />
      
      <header className="main-container app-header py-6 flex justify-between items-center">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="app-title bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
            0Pirate
          </h1>
          <p className="app-tagline">Secure & Refactor Your Code with AI</p>
        </motion.div>
        
        {user && (
          <motion.button 
            onClick={() => setPanelOpen(true)} 
            className="btn btn-secondary group"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <User size={16} className="group-hover:scale-110 transition-transform" /> 
            Account
          </motion.button>
        )}
      </header>

      <div className="main-container flex-grow flex flex-col">
        {renderView()}
      </div>
    </div>
  );
}