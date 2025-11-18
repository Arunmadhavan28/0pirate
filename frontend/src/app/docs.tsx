// app/docs.tsx
"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Link from 'next/link';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import {
  Info,
  AlertTriangle,
  Lightbulb,
  Code,
  Github,
  Shield,
  KeyRound,
  Bot,
  BookOpen,
  LayoutDashboard,
  MessageCircle,
  Users,
  ChevronLeft,
  ChevronRight,
  Terminal,
  Settings,
  Cpu,
  Search,
  Zap,
  Lock,
  Globe,
  Rocket,
  CheckCircle,
  Play,
  Copy,
  ExternalLink,
  FileText,
  BarChart3,
  Server
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Enhanced Reusable Components ---

const CodeBlock = React.memo(({ 
  language, 
  children, 
  showLineNumbers = true,
  className = "" 
}: { 
  language: string; 
  children: string;
  showLineNumbers?: boolean;
  className?: string;
}) => {
  const code = children.trim();
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code: ', err);
    }
  };

  return (
    <div className={`my-6 rounded-xl bg-gray-900 border border-gray-700 overflow-hidden group relative ${className}`}>
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <span className="text-xs font-mono text-gray-400 uppercase tracking-wide">
          {language}
        </span>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-2 px-3 py-1 text-xs text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-700"
        >
          {copied ? (
            <CheckCircle size={14} className="text-green-400" />
          ) : (
            <Copy size={14} />
          )}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={atomOneDark}
        customStyle={{
          background: 'transparent',
          padding: '1.5rem',
          margin: 0,
          fontSize: '0.875rem',
          lineHeight: '1.6'
        }}
        showLineNumbers={showLineNumbers}
        wrapLongLines={false}
        PreTag="div"
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
});
CodeBlock.displayName = 'CodeBlock';

const Callout = ({ 
  type = 'info', 
  children,
  title 
}: { 
  type?: 'info' | 'warning' | 'tip' | 'success' | 'danger';
  children: React.ReactNode;
  title?: string;
}) => {
  const styles = {
    info: { 
      icon: Info, 
      bg: 'bg-blue-900/20', 
      border: 'border-blue-500/30', 
      text: 'text-blue-300',
      accent: 'bg-blue-500'
    },
    warning: { 
      icon: AlertTriangle, 
      bg: 'bg-yellow-900/20', 
      border: 'border-yellow-500/30', 
      text: 'text-yellow-300',
      accent: 'bg-yellow-500'
    },
    tip: { 
      icon: Lightbulb, 
      bg: 'bg-green-900/20', 
      border: 'border-green-500/30', 
      text: 'text-green-300',
      accent: 'bg-green-500'
    },
    success: { 
      icon: CheckCircle, 
      bg: 'bg-green-900/20', 
      border: 'border-green-500/30', 
      text: 'text-green-300',
      accent: 'bg-green-500'
    },
    danger: { 
      icon: AlertTriangle, 
      bg: 'bg-red-900/20', 
      border: 'border-red-500/30', 
      text: 'text-red-300',
      accent: 'bg-red-500'
    }
  };
  
  const { icon: Icon, bg, border, text, accent } = styles[type];
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`my-6 p-5 rounded-xl border-l-4 ${border} ${bg} ${text} flex items-start gap-4 relative overflow-hidden`}
      style={{ borderLeftColor: `var(--${type}-color)` }}
    >
      <div className={`w-1 h-full absolute left-0 top-0 ${accent}`} />
      <Icon size={20} className="mt-0.5 flex-shrink-0 z-10" />
      <div className="flex-1">
        {title && <h4 className="font-semibold mb-2 text-current">{title}</h4>}
        <div className="prose-doc text-sm">{children}</div>
      </div>
    </motion.div>
  );
};

const ApiEndpoint = ({ 
  method, 
  path, 
  description, 
  headers, 
  bodyParams, 
  responseExample,
  note 
}: {
  method: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH';
  path: string;
  description: string;
  headers?: { key: string; description: string; required?: boolean }[];
  bodyParams?: { key: string; type: string; description: string; required?: boolean }[];
  responseExample: string;
  note?: string;
}) => {
  const methodColors = {
    GET: 'text-blue-400 border-blue-400 bg-blue-900/20',
    POST: 'text-green-400 border-green-400 bg-green-900/20',
    DELETE: 'text-red-400 border-red-400 bg-red-900/20',
    PUT: 'text-yellow-400 border-yellow-400 bg-yellow-900/20',
    PATCH: 'text-purple-400 border-purple-400 bg-purple-900/20',
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-8 p-6 rounded-xl border border-gray-700 bg-gray-900/30 backdrop-blur-sm"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:gap-4 mb-4">
        <span className={`px-3 py-1 rounded-md text-sm font-semibold border ${methodColors[method]} w-fit flex items-center gap-2`}>
          <span className="w-2 h-2 rounded-full bg-current"></span>
          {method}
        </span>
        <code className="text-lg font-mono text-gray-300 mt-2 sm:mt-0 bg-gray-800 px-3 py-1 rounded-md">
          {path}
        </code>
      </div>
      
      <p className="text-gray-400 mb-6 leading-relaxed">{description}</p>

      {note && (
        <Callout type="info" className="mb-6">
          {note}
        </Callout>
      )}

      {headers && headers.length > 0 && (
        <div className="mb-6">
          <h4 className="font-semibold mb-3 text-gray-200 flex items-center gap-2">
            <FileText size={16} />
            Headers
          </h4>
          <div className="space-y-3">
            {headers.map((h, index) => (
              <motion.div 
                key={h.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/50"
              >
                <code className="text-purple-400 font-mono text-sm flex-shrink-0">
                  {h.key}
                </code>
                <div className="flex-1">
                  <span className="text-gray-300 text-sm">{h.description}</span>
                  {h.required && (
                    <span className="ml-2 px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full">
                      Required
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {bodyParams && bodyParams.length > 0 && (
        <div className="mb-6">
          <h4 className="font-semibold mb-3 text-gray-200 flex items-center gap-2">
            <Settings size={16} />
            Body Parameters
          </h4>
          <div className="space-y-3">
            {bodyParams.map((p, index) => (
              <motion.div 
                key={p.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/50"
              >
                <div className="flex-shrink-0">
                  <code className="text-purple-400 font-mono text-sm block">
                    {p.key}
                  </code>
                  <span className="text-cyan-400 text-xs font-mono mt-1 block">
                    {p.type}
                  </span>
                </div>
                <div className="flex-1">
                  <span className="text-gray-300 text-sm">{p.description}</span>
                  {p.required && (
                    <span className="ml-2 px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full">
                      Required
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h4 className="font-semibold mb-3 text-gray-200 flex items-center gap-2">
          <Code size={16} />
          Example Response
        </h4>
        <CodeBlock language="json" showLineNumbers={true}>
          {responseExample}
        </CodeBlock>
      </div>
    </motion.div>
  );
};

const FeatureCard = ({ 
  icon: Icon, 
  title, 
  description,
  color = "blue" 
}: { 
  icon: React.ElementType;
  title: string;
  description: string;
  color?: "blue" | "green" | "purple" | "orange" | "red";
}) => {
  const colorClasses = {
    blue: 'from-blue-500/10 to-blue-600/10 border-blue-500/20 text-blue-400',
    green: 'from-green-500/10 to-green-600/10 border-green-500/20 text-green-400',
    purple: 'from-purple-500/10 to-purple-600/10 border-purple-500/20 text-purple-400',
    orange: 'from-orange-500/10 to-orange-600/10 border-orange-500/20 text-orange-400',
    red: 'from-red-500/10 to-red-600/10 border-red-500/20 text-red-400'
  };

  return (
    <motion.div
      whileHover={{ y: -5, scale: 1.02 }}
      className={`p-6 rounded-xl border bg-gradient-to-br ${colorClasses[color]} backdrop-blur-sm hover:shadow-xl transition-all duration-300`}
    >
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg bg-${color}-500/20`}>
          <Icon size={20} />
        </div>
        <h3 className="font-semibold text-lg text-white">{title}</h3>
      </div>
      <p className="text-gray-300 text-sm leading-relaxed">{description}</p>
    </motion.div>
  );
};

const SearchBar = ({ onSearch }: { onSearch: (query: string) => void }) => {
  const [query, setQuery] = useState('');

  return (
    <div className="relative mb-8">
      <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
      <input
        type="text"
        placeholder="Search documentation... (e.g., API keys, setup, security)"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          onSearch(e.target.value);
        }}
        className="w-full pl-12 pr-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
      />
    </div>
  );
};

// --- Enhanced Sidebar with Search ---
const SidebarNav = ({ 
  activeTab, 
  onBack,
  searchQuery,
  onSearchChange 
}: { 
  activeTab: 'user' | 'dev';
  onBack?: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}) => {
  const userSections = [
    { id: 'introduction', title: 'Introduction', icon: Info },
    { id: 'quick-start', title: 'Quick Start Guide', icon: Rocket },
    { id: 'web-app-usage', title: 'Web App Usage', icon: LayoutDashboard },
    { id: 'security-model', title: 'Security Model', icon: Shield },
    { id: 'supported-models', title: 'AI Models', icon: Cpu },
    { id: 'use-cases', title: 'Use Cases', icon: BarChart3 },
    { id: 'support', title: 'Support', icon: MessageCircle }
  ];
  
  const devSections = [
    { id: 'introduction', title: 'Introduction', icon: Info },
    { id: 'api-reference', title: 'API Reference', icon: Code },
    { id: 'github-action', title: 'GitHub Action', icon: Github },
    { id: 'llm-perspective', title: 'LLM Perspective', icon: Bot },
    { id: 'security-model', title: 'Security Model', icon: Shield },
    { id: 'supported-models', title: 'AI Models', icon: Cpu },
    { id: 'api-keys', title: 'API Keys', icon: KeyRound },
    { id: 'best-practices', title: 'Best Practices', icon: CheckCircle }
  ];

  const sections = activeTab === 'user' ? userSections : devSections;
  const [activeSection, setActiveSection] = useState('introduction');
  const [isOpen, setIsOpen] = useState(true);
  const sectionRefs = useRef<Record<string, HTMLElement>>({});
  const throttleRef = useRef<NodeJS.Timeout | null>(null);

  const filteredSections = useMemo(() => {
    if (!searchQuery) return sections;
    return sections.filter(section => 
      section.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      section.id.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [sections, searchQuery]);

  const handleScrollTo = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
    setActiveSection(id);
  };

  const onScroll = useCallback(() => {
    if (throttleRef.current) return;

    throttleRef.current = setTimeout(() => {
      let currentSection = 'introduction';
      const scrollPos = window.scrollY + 100;

      for (const section of sections) {
        const el = sectionRefs.current[section.id];
        if (el && el.offsetTop <= scrollPos) {
          currentSection = section.id;
        }
      }
      setActiveSection(currentSection);
      throttleRef.current = null;
    }, 100);
  }, [sections]);

  useEffect(() => {
    window.addEventListener('scroll', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (throttleRef.current) {
        clearTimeout(throttleRef.current);
      }
    };
  }, [onScroll]);

  return (
    <aside className={`bg-gray-900 text-white transition-all duration-300 ${isOpen ? 'w-80' : 'w-20'} sticky top-0 h-screen overflow-y-auto border-r border-gray-800 flex flex-col`}>
      <div className="p-4 border-b border-gray-800">
        {onBack && (
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors w-full mb-4 group"
          >
            <ChevronLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
            {isOpen && <span>Back to Home</span>}
          </button>
        )}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center space-x-2 text-gray-300 hover:text-white mb-4 w-full group"
        >
          {isOpen ? (
            <ChevronLeft size={20} className="text-gray-500 group-hover:text-white transition-colors" />
          ) : (
            <ChevronRight size={20} className="text-gray-500 group-hover:text-white transition-colors" />
          )}
          {isOpen && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Lock size={16} />
              </div>
              <span className="text-xl font-bold text-white bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                0Pirate Docs
              </span>
            </div>
          )}
        </button>
        
        {isOpen && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        )}
      </div>

      <nav className="p-4 space-y-1 flex-grow">
        <span className="px-2 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {isOpen ? (activeTab === 'user' ? 'User Guide' : 'Developer Guide') : (activeTab === 'user' ? 'USER' : 'DEV')}
        </span>
        {filteredSections.map((section) => {
          const Icon = section.icon;
          const isActive = activeSection === section.id;
          return (
            <Link
              key={section.id}
              href={`#${section.id}`}
              onClick={(e) => handleScrollTo(e, section.id)}
              className={`flex items-center space-x-3 px-3 py-3 rounded-xl transition-all duration-200 group ${
                isOpen ? 'w-full' : 'justify-center'
              } ${
                isActive
                  ? 'bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-blue-300 border-l-2 border-blue-500'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
              title={isOpen ? '' : section.title}
            >
              <Icon size={18} className="flex-shrink-0" />
              {isOpen && (
                <span className="text-sm font-medium flex-1">{section.title}</span>
              )}
              {isActive && isOpen && (
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              )}
            </Link>
          );
        })}
        
        {filteredSections.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <Search size={24} className="mx-auto mb-2" />
            <p className="text-sm">No results found</p>
          </div>
        )}
      </nav>
      
      {isOpen && (
        <div className="p-4 border-t border-gray-800">
          <div className="text-xs text-gray-500 text-center">
            © 2024 0Pirate.com
          </div>
        </div>
      )}
    </aside>
  );
};

// --- Enhanced Layout Wrapper ---
const DocsLayout = ({ 
  children, 
  activeTab, 
  onBack,
  searchQuery,
  onSearchChange 
}: {
  children: (refs: React.RefObject<Record<string, HTMLElement>>) => React.ReactNode;
  activeTab: 'user' | 'dev';
  onBack?: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}) => {
  const sectionRefs = useRef<Record<string, HTMLElement>>({});

  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      <style>{`
        :root {
          --info-color: #3b82f6;
          --warning-color: #f59e0b;
          --tip-color: #10b981;
          --success-color: #10b981;
          --danger-color: #ef4444;
        }
        
        .prose-doc {
          color: #A0A0A0;
          line-height: 1.7;
        }
        .prose-doc p, .prose-doc ul, .prose-doc ol {
          margin-bottom: 1.25em;
        }
        .prose-doc h1 {
          font-size: 3rem;
          font-weight: 800;
          background: linear-gradient(135deg, #EAEAEA 0%, #A0A0A0 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          margin-bottom: 2rem;
          margin-top: 0;
          padding-bottom: 0.5rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .prose-doc h2 {
          font-size: 2rem;
          font-weight: 700;
          color: #EAEAEA;
          margin-bottom: 1.5rem;
          margin-top: 3rem;
          padding-bottom: 0.5rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .prose-doc h3 {
          font-size: 1.5rem;
          font-weight: 600;
          color: #EAEAEA;
          margin-bottom: 1rem;
          margin-top: 2.5rem;
        }
        .prose-doc h4 {
          font-size: 1.125rem;
          font-weight: 600;
          color: #EAEAEA;
          margin-bottom: 0.5rem;
        }
        .prose-doc a {
          color: #3B82F6;
          text-decoration: none;
          font-weight: 500;
        }
        .prose-doc a:hover {
          text-decoration: underline;
        }
        .prose-doc code {
          color: #f472b6;
          background-color: rgba(244, 114, 182, 0.1);
          padding: 0.2em 0.4em;
          border-radius: 0.25rem;
          font-size: 0.9em;
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        }
        .prose-doc ul {
          list-style: none;
          padding-left: 0.5rem;
        }
        .prose-doc ol {
          list-style: none;
          padding-left: 0.5rem;
          counter-reset: list-counter;
        }
        .prose-doc li {
          margin-bottom: 0.75em;
          position: relative;
          padding-left: 1.75rem;
        }
        .prose-doc ul > li::before {
          content: '•';
          position: absolute;
          left: 0.5rem;
          color: #3B82F6;
          font-weight: bold;
        }
        .prose-doc ol > li::before {
          content: counter(list-counter) ".";
          counter-increment: list-counter;
          position: absolute;
          left: 0.5rem;
          color: #3B82F6;
          font-weight: bold;
        }
        .scroll-mt-20 {
          scroll-margin-top: 5rem;
        }
        
        /* Smooth scrolling */
        html {
          scroll-behavior: smooth;
        }
        
        /* Custom selection */
        ::selection {
          background: rgba(59, 130, 246, 0.3);
        }
      `}</style>
      <div className="flex">
        <SidebarNav 
          activeTab={activeTab} 
          onBack={onBack}
          searchQuery={searchQuery}
          onSearchChange={onSearchChange}
        />
        <main className="flex-1 p-8 md:p-12 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            {children(sectionRefs)}
          </div>
        </main>
      </div>
    </div>
  );
};

// --- Enhanced Page Content Sections ---

const Introduction = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="introduction" ref={el => setRef('introduction', el)} className="mb-16 scroll-mt-20">
    <motion.div 
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      <div className="prose-doc">
        <h1>
          <Info size={40} className="inline-block mr-3 text-blue-400" />
          0Pirate Documentation
        </h1>
        <p className="text-xl text-gray-400 leading-relaxed mb-6">
          Welcome to <strong className="text-white">0Pirate</strong> - the enterprise-grade AI gateway for secure code analysis and transformation. Built on a <strong className="text-green-400">Zero-Trust security model</strong>, 0Pirate ensures your intellectual property remains protected while leveraging the power of advanced AI models.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-8">
          <FeatureCard
            icon={Shield}
            title="Zero-Trust Security"
            description="Your source code never leaves your control. Advanced abstraction protects intellectual property."
            color="green"
          />
          <FeatureCard
            icon={Cpu}
            title="Multi-Model Support"
            description="Connect to Gemini, GPT, Claude, Ollama, and more with unified security layers."
            color="blue"
          />
          <FeatureCard
            icon={Zap}
            title="Enterprise Ready"
            description="GitHub Actions, CI/CD integration, and scalable architecture for teams."
            color="purple"
          />
        </div>

        <Callout type="tip" title="Why 0Pirate?">
          <p><strong>Traditional AI tools risk your IP</strong> by sending raw code to third-party providers. <strong>0Pirate is fundamentally different</strong> - we transform your code into secure abstract representations that preserve logic while removing sensitive information.</p>
        </Callout>

        <div className="bg-gradient-to-r from-gray-900 to-gray-800 p-6 rounded-xl border border-gray-700 my-8">
          <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Rocket size={24} className="text-blue-400" />
            Get Started in 60 Seconds
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div className="p-4">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-white font-bold text-sm">1</span>
              </div>
              <p className="text-sm text-gray-300">Sign up at 0Pirate.com</p>
            </div>
            <div className="p-4">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-white font-bold text-sm">2</span>
              </div>
              <p className="text-sm text-gray-300">Configure your AI providers</p>
            </div>
            <div className="p-4">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-white font-bold text-sm">3</span>
              </div>
              <p className="text-sm text-gray-300">Start secure code analysis</p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  </section>
);

const QuickStart = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="quick-start" ref={el => setRef('quick-start', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Rocket size={30} className="text-orange-400" />Quick Start Guide</h2>
      
      <h3>1. Create Your 0Pirate Account</h3>
      <p>Start by signing up at <a href="https://0pirate.com" target="_blank" rel="noopener noreferrer">0Pirate.com</a>. The free tier includes generous limits for testing and small projects.</p>
      
      <h3>2. Configure Your First AI Provider</h3>
      <p>Add your AI API keys in the dashboard. Here's how to set up Google Gemini:</p>
      
      <CodeBlock language="bash">
{`# Navigate to Account > API Keys
# Select "Google Gemini" as provider
# Name: "My Gemini Key"
# Paste your Google AI Studio API key
# Click "Save Key"`}
      </CodeBlock>

      <h3>3. Test with Sample Code</h3>
      <p>Try this example to see 0Pirate in action:</p>
      
      <CodeBlock language="python" title="sample_code.py">
{`import os
import requests

def fetch_user_data(user_id):
    """
    Fetch user data from API
    """
    api_key = os.environ.get('API_SECRET_KEY')  # This gets redacted
    response = requests.get(
        f"https://api.example.com/users/{user_id}",
        headers={'Authorization': f'Bearer {api_key}'}
    )
    return response.json()

def process_sensitive_data(data):
    # Process user data
    email = data.get('email')  # This gets abstracted
    name = data.get('name')    # This gets abstracted
    return f"Processed: {name} <{email}>"`}
      </CodeBlock>

      <h3>4. Run Your First Analysis</h3>
      <p>In the web app:</p>
      <ol>
        <li>Paste the sample code above</li>
        <li>Select "Code Review" as the task</li>
        <li>Choose "gemini" as provider</li>
        <li>Select your saved Gemini key</li>
        <li>Click "Run Analysis"</li>
      </ol>

      <Callout type="success" title="You're All Set!">
        <p>Within seconds, you'll see how 0Pirate transforms your code for security and provides AI-powered insights without exposing your intellectual property.</p>
      </Callout>
    </div>
  </section>
);

const WebAppUsage = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="web-app-usage" ref={el => setRef('web-app-usage', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><LayoutDashboard size={30} className="text-purple-400" />Web App Usage</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 my-8">
        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-white">Core Workflow</h3>
          
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-white text-xs font-bold">1</span>
              </div>
              <div>
                <h4 className="font-semibold text-white">Input Code</h4>
                <p className="text-gray-400 text-sm">Paste code snippets or upload files/ZIP archives for multi-file projects.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-white text-xs font-bold">2</span>
              </div>
              <div>
                <h4 className="font-semibold text-white">Add Context</h4>
                <p className="text-gray-400 text-sm">Provide error logs, stack traces, or specific requirements for better AI understanding.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-white text-xs font-bold">3</span>
              </div>
              <div>
                <h4 className="font-semibold text-white">Configure Analysis</h4>
                <p className="text-gray-400 text-sm">Select task, AI model, and security settings tailored to your needs.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-white text-xs font-bold">4</span>
              </div>
              <div>
                <h4 className="font-semibold text-white">Review Results</h4>
                <p className="text-gray-400 text-sm">Get AI analysis and transformed code with full context preservation.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl p-6 border border-gray-700">
          <h3 className="text-xl font-semibold text-white mb-4">Available Tasks</h3>
          <div className="space-y-3">
            {[
              { task: 'Fix Code', desc: 'Debug and fix errors in your code' },
              { task: 'Code Review', desc: 'Get security and best practice reviews' },
              { task: 'Refactor', desc: 'Improve code structure and performance' },
              { task: 'Document', desc: 'Generate comprehensive documentation' },
              { task: 'Optimize', desc: 'Performance and memory optimization' },
              { task: 'Security Audit', desc: 'Deep security vulnerability analysis' }
            ].map((item, index) => (
              <motion.div 
                key={item.task}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 transition-colors"
              >
                <CheckCircle size={16} className="text-green-400 flex-shrink-0" />
                <div>
                  <span className="text-white font-medium text-sm">{item.task}</span>
                  <p className="text-gray-400 text-xs">{item.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <Callout type="info" title="Pro Tip: Multi-File Analysis">
        <p>For complex projects, upload ZIP files containing your entire codebase. 0Pirate will analyze relationships between files and provide comprehensive insights across your entire project structure.</p>
      </Callout>
    </div>
  </section>
);

const SecurityModel = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="security-model" ref={el => setRef('security-model', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Shield size={30} className="text-green-400" />Security Model</h2>
      
      <div className="bg-gradient-to-r from-green-900/20 to-blue-900/20 p-6 rounded-xl border border-green-500/30 my-6">
        <h3 className="text-xl font-semibold text-white mb-4">Zero-Trust Architecture</h3>
        <p className="text-gray-300 mb-4">
          0Pirate operates on a <strong>Zero-Trust security model</strong> where your source code is never transmitted to AI providers in its original form. Instead, we create abstract representations that preserve logic while removing sensitive information.
        </p>
      </div>

      <h3>How Code Abstraction Works</h3>
      <p>When you submit code to 0Pirate, our system:</p>
      <ol>
        <li><strong>Tokenizes</strong> your code into logical components</li>
        <li><strong>Abstracts</strong> sensitive data (API keys, credentials, IP addresses)</li>
        <li><strong>Preserves</strong> code structure, logic flow, and relationships</li>
        <li><strong>Creates</strong> a secure representation for AI processing</li>
        <li><strong>Reconstructs</strong> the AI response back into your original code context</li>
      </ol>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">
        <div className="bg-red-900/20 p-4 rounded-lg border border-red-500/30">
          <h4 className="font-semibold text-red-400 mb-2">❌ Traditional AI Tools</h4>
          <ul className="text-sm text-gray-300 space-y-1">
            <li>• Send raw source code to providers</li>
            <li>• Risk IP and credential exposure</li>
            <li>• No control over data retention</li>
            <li>• Compliance challenges</li>
          </ul>
        </div>
        
        <div className="bg-green-900/20 p-4 rounded-lg border border-green-500/30">
          <h4 className="font-semibold text-green-400 mb-2">✅ 0Pirate Approach</h4>
          <ul className="text-sm text-gray-300 space-y-1">
            <li>• Abstract representations only</li>
            <li>• Zero raw code transmission</li>
            <li>• Built-in credential redaction</li>
            <li>• Enterprise compliance ready</li>
          </ul>
        </div>
      </div>

      <h3>Data Protection Features</h3>
      <div className="space-y-4 my-6">
        {[
          {
            feature: "Automatic Credential Redaction",
            description: "API keys, passwords, and tokens are automatically detected and removed from AI submissions"
          },
          {
            feature: "Abstract Syntax Tree (AST) Transformation",
            description: "Code is parsed into AST and transformed into logical representations"
          },
          {
            feature: "Context-Aware Processing",
            description: "Code relationships and dependencies are preserved while removing sensitive implementation details"
          },
          {
            feature: "No Data Persistence",
            description: "Your code is processed in memory and never stored on our servers"
          }
        ].map((item, index) => (
          <motion.div 
            key={item.feature}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="flex items-start gap-3 p-4 rounded-lg bg-gray-800/50 border border-gray-700"
          >
            <Shield size={18} className="text-green-400 mt-0.5 flex-shrink-0" />
            <div>
              <h4 className="font-semibold text-white text-sm">{item.feature}</h4>
              <p className="text-gray-400 text-sm mt-1">{item.description}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <Callout type="warning" title="Important Security Note">
        <p>While 0Pirate provides advanced security abstraction, always follow security best practices:</p>
        <ul>
          <li>Never hardcode credentials in your source code</li>
          <li>Use environment variables for sensitive configuration</li>
          <li>Regularly rotate API keys and access tokens</li>
          <li>Implement proper access controls in your codebase</li>
        </ul>
      </Callout>
    </div>
  </section>
);

const SupportedModels = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="supported-models" ref={el => setRef('supported-models', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Cpu size={30} className="text-cyan-400" />Supported AI Models</h2>
      
      <p>0Pirate supports a wide range of AI providers through a unified security layer. Configure multiple providers and switch between them seamlessly.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 my-8">
        {[
          {
            name: "Google Gemini",
            description: "Google's advanced multimodal AI model",
            status: "Fully Supported",
            color: "text-blue-400",
            icon: "🤖"
          },
          {
            name: "OpenAI GPT",
            description: "GPT-4, GPT-3.5 Turbo, and other OpenAI models",
            status: "Fully Supported",
            color: "text-green-400",
            icon: "🧠"
          },
          {
            name: "Anthropic Claude",
            description: "Claude 3, Claude 2, and Claude Instant",
            status: "Fully Supported",
            color: "text-purple-400",
            icon: "💡"
          },
          {
            name: "Ollama",
            description: "Local models through Ollama integration",
            status: "Fully Supported",
            color: "text-orange-400",
            icon: "🏠"
          },
          {
            name: "Azure OpenAI",
            description: "Enterprise OpenAI through Azure",
            status: "Beta",
            color: "text-blue-300",
            icon: "☁️"
          },
          {
            name: "Custom Endpoints",
            description: "Any OpenAI-compatible API endpoint",
            status: "Fully Supported",
            color: "text-gray-400",
            icon: "🔧"
          }
        ].map((model, index) => (
          <motion.div 
            key={model.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-gray-900 rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-white">{model.name}</h3>
              <span className="text-2xl">{model.icon}</span>
            </div>
            <p className="text-gray-400 text-sm mb-3">{model.description}</p>
            <div className="flex items-center justify-between">
              <span className={`text-xs px-2 py-1 rounded-full ${model.color} bg-gray-800`}>
                {model.status}
              </span>
              <button className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                Configure →
              </button>
            </div>
          </motion.div>
        ))}
      </div>

      <h3>Model Configuration Example</h3>
      <p>Configure multiple AI providers in your account settings:</p>
      
      <CodeBlock language="json" title="Configuration Example">
{`{
  "providers": {
    "gemini": {
      "api_key": "your_gemini_key_here",
      "model": "gemini-pro",
      "enabled": true
    },
    "openai": {
      "api_key": "your_openai_key_here", 
      "model": "gpt-4",
      "enabled": true
    },
    "claude": {
      "api_key": "your_claude_key_here",
      "model": "claude-3-sonnet-20240229",
      "enabled": false
    }
  }
}`}
      </CodeBlock>

      <Callout type="tip" title="Model Selection Strategy">
        <p><strong>Gemini Pro</strong> excels at code analysis and is cost-effective. <strong>GPT-4</strong> provides superior reasoning for complex problems. <strong>Claude</strong> offers excellent context handling for large codebases. Use <strong>Ollama</strong> for completely private, offline processing.</p>
      </Callout>
    </div>
  </section>
);

const UseCases = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="use-cases" ref={el => setRef('use-cases', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><BarChart3 size={30} className="text-yellow-400" />Use Cases</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 my-8">
        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-white">Individual Developers</h3>
          
          {[
            {
              title: "Code Review Assistant",
              description: "Get instant security and quality reviews before committing code"
            },
            {
              title: "Debugging Partner", 
              description: "Quickly identify and fix complex bugs with AI assistance"
            },
            {
              title: "Learning Tool",
              description: "Understand unfamiliar codebases and programming concepts"
            },
            {
              title: "Documentation Generator",
              description: "Automatically create comprehensive documentation for your projects"
            }
          ].map((useCase, index) => (
            <motion.div 
              key={useCase.title}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="flex items-start gap-3 p-4 rounded-lg bg-gray-800/50 border border-gray-700"
            >
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-xs font-bold">{index + 1}</span>
              </div>
              <div>
                <h4 className="font-semibold text-white text-sm">{useCase.title}</h4>
                <p className="text-gray-400 text-sm mt-1">{useCase.description}</p>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-white">Teams & Enterprises</h3>
          
          {[
            {
              title: "CI/CD Integration",
              description: "Automate code reviews and security checks in your pipeline"
            },
            {
              title: "Knowledge Sharing",
              description: "Standardize code quality and best practices across teams"
            },
            {
              title: "Security Compliance",
              description: "Ensure code meets security standards without manual review"
            },
            {
              title: "Onboarding Acceleration",
              description: "Help new developers understand complex codebases faster"
            }
          ].map((useCase, index) => (
            <motion.div 
              key={useCase.title}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="flex items-start gap-3 p-4 rounded-lg bg-gray-800/50 border border-gray-700"
            >
              <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-xs font-bold">{index + 1}</span>
              </div>
              <div>
                <h4 className="font-semibold text-white text-sm">{useCase.title}</h4>
                <p className="text-gray-400 text-sm mt-1">{useCase.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      <h3>Real-World Success Stories</h3>
      <div className="space-y-4 my-6">
        {[
          {
            company: "FinTech Startup",
            challenge: "Needed to ensure PCI compliance in payment processing code",
            solution: "Used 0Pirate security audits to automatically detect compliance issues",
            result: "Reduced manual review time by 80% while improving security"
          },
          {
            company: "Healthcare SaaS",
            challenge: "HIPAA compliance requirements for patient data handling",
            solution: "Integrated 0Pirate into CI/CD for automated HIPAA compliance checks",
            result: "Achieved compliance certification 3x faster than projected"
          },
          {
            company: "E-commerce Platform", 
            challenge: "Large legacy codebase with security vulnerabilities",
            solution: "Used 0Pirate to systematically identify and fix security issues",
            result: "Fixed 95% of critical vulnerabilities in first 30 days"
          }
        ].map((story, index) => (
          <motion.div 
            key={story.company}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.2 }}
            className="p-5 rounded-xl border border-gray-700 bg-gray-900/30"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <h4 className="font-semibold text-white">{story.company}</h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-500 text-xs">Challenge</span>
                <p className="text-gray-300">{story.challenge}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Solution</span>
                <p className="text-gray-300">{story.solution}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Result</span>
                <p className="text-gray-300">{story.result}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

const Support = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="support" ref={el => setRef('support', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><MessageCircle size={30} className="text-blue-400" />Support & Community</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 my-8">
        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-white">Get Help</h3>
          
          {[
            {
              title: "Documentation",
              description: "Comprehensive guides and API references",
              action: "Browse Docs",
              icon: BookOpen,
              color: "text-blue-400"
            },
            {
              title: "Community Forum",
              description: "Ask questions and share knowledge",
              action: "Join Forum", 
              icon: Users,
              color: "text-green-400"
            },
            {
              title: "GitHub Issues",
              description: "Report bugs and request features",
              action: "Open Issue",
              icon: Github,
              color: "text-purple-400"
            },
            {
              title: "Email Support",
              description: "Direct support for technical issues",
              action: "Contact Support",
              icon: MessageCircle,
              color: "text-orange-400"
            }
          ].map((item, index) => {
            const Icon = item.icon;
            return (
              <motion.div 
                key={item.title}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-start gap-4 p-4 rounded-lg bg-gray-800/50 border border-gray-700 hover:border-gray-600 transition-colors"
              >
                <Icon size={20} className={`mt-0.5 ${item.color}`} />
                <div className="flex-1">
                  <h4 className="font-semibold text-white text-sm">{item.title}</h4>
                  <p className="text-gray-400 text-sm mt-1">{item.description}</p>
                </div>
                <button className="text-xs text-blue-400 hover:text-blue-300 transition-colors whitespace-nowrap">
                  {item.action} →
                </button>
              </motion.div>
            );
          })}
        </div>

        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-white">Resources</h3>
          
          <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 p-5 rounded-xl border border-blue-500/30">
            <h4 className="font-semibold text-white mb-3">Quick Links</h4>
            <div className="space-y-3">
              {[
                { name: "API Reference", url: "#api-reference" },
                { name: "GitHub Action", url: "#github-action" },
                { name: "Security Model", url: "#security-model" },
                { name: "Best Practices", url: "#best-practices" }
              ].map((link, index) => (
                <Link 
                  key={link.name}
                  href={link.url}
                  className="flex items-center gap-2 text-sm text-gray-300 hover:text-white transition-colors group"
                >
                  <ChevronRight size={14} className="group-hover:translate-x-1 transition-transform" />
                  {link.name}
                </Link>
              ))}
            </div>
          </div>

          <div className="bg-gray-900 p-5 rounded-xl border border-gray-700">
            <h4 className="font-semibold text-white mb-3">Status & Updates</h4>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Service Status</span>
                <span className="text-green-400 flex items-center gap-1">
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  Operational
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Last Updated</span>
                <span className="text-gray-300">Today</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Version</span>
                <span className="text-gray-300">v2.4.1</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Callout type="info" title="Enterprise Support">
        <p>For enterprise customers, we offer dedicated support, custom integrations, and SLAs. Contact our sales team to learn more about enterprise features and support options.</p>
      </Callout>
    </div>
  </section>
);

// --- Developer Documentation Sections ---

const ApiReference = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="api-reference" ref={el => setRef('api-reference', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Code size={30} className="text-green-400" />API Reference</h2>
      
      <p>The 0Pirate API provides programmatic access to all platform features. All API endpoints require authentication via API keys and follow REST conventions.</p>

      <Callout type="info" title="Base URL">
        <p>All API requests should be made to: <code>https://api.0pirate.com/v1</code></p>
      </Callout>

      <h3>Authentication</h3>
      <p>Include your API key in the request headers:</p>
      
      <CodeBlock language="bash">
{`curl -X GET "https://api.0pirate.com/v1/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json"`}
      </CodeBlock>

      <h3>Core Endpoints</h3>

      <ApiEndpoint
        method="POST"
        path="/analyze"
        description="Submit code for AI analysis with security abstraction"
        headers={[
          { key: "Authorization", description: "Bearer token API key", required: true },
          { key: "Content-Type", description: "application/json", required: true }
        ]}
        bodyParams={[
          { key: "code", type: "string", description: "Source code to analyze", required: true },
          { key: "task", type: "string", description: "Analysis type (fix, review, refactor, etc.)", required: true },
          { key: "provider", type: "string", description: "AI provider (gemini, openai, claude, etc.)", required: true },
          { key: "context", type: "string", description: "Additional context or requirements", required: false },
          { key: "language", type: "string", description: "Programming language for better analysis", required: false }
        ]}
        responseExample={`{
  "id": "analysis_123456",
  "status": "completed",
  "result": {
    "analysis": "The code contains a potential security vulnerability...",
    "suggested_fix": "Consider using parameterized queries...",
    "confidence": 0.92,
    "abstracted_code": "function processUserData(userId) {...}"
  },
  "provider_used": "gemini",
  "processing_time": 2.34,
  "credits_used": 1
}`}
        note="Code is automatically abstracted for security before being sent to AI providers"
      />

      <ApiEndpoint
        method="GET"
        path="/analysis/{id}"
        description="Retrieve analysis results by ID"
        headers={[
          { key: "Authorization", description: "Bearer token API key", required: true }
        ]}
        responseExample={`{
  "id": "analysis_123456",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:02Z",
  "result": {
    "analysis": "Security review completed...",
    "suggested_fix": "Implement input validation...",
    "confidence": 0.95
  }
}`}
      />

      <ApiEndpoint
        method="GET"
        path="/providers"
        description="List configured AI providers and their status"
        headers={[
          { key: "Authorization", description: "Bearer token API key", required: true }
        ]}
        responseExample={`{
  "providers": [
    {
      "name": "gemini",
      "enabled": true,
      "models": ["gemini-pro", "gemini-pro-vision"],
      "rate_limit": 1000,
      "used_this_month": 245
    },
    {
      "name": "openai", 
      "enabled": true,
      "models": ["gpt-4", "gpt-3.5-turbo"],
      "rate_limit": 500,
      "used_this_month": 189
    }
  ]
}`}
      />

      <h3>Error Handling</h3>
      <p>The API uses standard HTTP status codes and returns detailed error messages:</p>
      
      <CodeBlock language="json">
{`{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please try again in 60 seconds.",
    "retry_after": 60,
    "details": {
      "limit": 1000,
      "remaining": 0,
      "reset_time": "2024-01-15T10:35:00Z"
    }
  }
}`}
      </CodeBlock>

      <div className="overflow-x-auto my-6">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Status Code</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Description</th>
            </tr>
          </thead>
          <tbody>
            {[
              { code: "200", description: "Success" },
              { code: "400", description: "Bad Request - Invalid parameters" },
              { code: "401", description: "Unauthorized - Invalid API key" },
              { code: "403", description: "Forbidden - Insufficient permissions" },
              { code: "429", description: "Too Many Requests - Rate limit exceeded" },
              { code: "500", description: "Internal Server Error" }
            ].map((row, index) => (
              <tr key={row.code} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="py-3 px-4">
                  <code className="text-purple-400">{row.code}</code>
                </td>
                <td className="py-3 px-4 text-gray-300">{row.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </section>
);

const GitHubAction = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="github-action" ref={el => setRef('github-action', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Github size={30} className="text-purple-400" />GitHub Action</h2>
      
      <p>Automate code analysis and security reviews in your CI/CD pipeline with the official 0Pirate GitHub Action.</p>

      <Callout type="tip" title="Perfect For">
        <p>Automated code reviews, security scanning, documentation generation, and quality gates in your pull request workflow.</p>
      </Callout>

      <h3>Quick Setup</h3>
      <p>Add this to your <code>.github/workflows/0pirate-analysis.yml</code>:</p>
      
      <CodeBlock language="yaml">
{`name: 0Pirate Code Analysis

on:
  pull_request:
    branches: [ main, develop ]
  push:
    branches: [ main ]

jobs:
  code-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: 0Pirate Analysis
        uses: 0pirate/analysis-action@v2
        with:
          api_key: \${{ secrets.ZERO_PIRATE_API_KEY }}
          task: 'review'
          provider: 'gemini'
          fail_on_issues: 'high'
          include_comments: true
        env:
          GITHUB_TOKEN: \${{ secrets.GITHUB_TOKEN }}`}
      </CodeBlock>

      <h3>Configuration Options</h3>
      <div className="overflow-x-auto my-6">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Input</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Required</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Default</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Description</th>
            </tr>
          </thead>
          <tbody>
            {[
              { input: "api_key", required: "Yes", default: "-", description: "Your 0Pirate API key" },
              { input: "task", required: "No", default: "review", description: "Analysis type: review, fix, security, document" },
              { input: "provider", required: "No", default: "gemini", description: "AI provider to use" },
              { input: "fail_on_issues", required: "No", default: "none", description: "Fail workflow on issues: none, high, medium, all" },
              { input: "include_comments", required: "No", default: "false", description: "Add review comments to PR" },
              { input: "max_issues", required: "No", default: "50", description: "Maximum number of issues to report" },
              { input: "exclude_patterns", required: "No", default: "", description: "Comma-separated glob patterns to exclude" }
            ].map((row, index) => (
              <tr key={row.input} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="py-3 px-4 font-mono text-purple-400 text-sm">{row.input}</td>
                <td className="py-3 px-4 text-gray-300">{row.required}</td>
                <td className="py-3 px-4 font-mono text-cyan-400 text-sm">{row.default}</td>
                <td className="py-3 px-4 text-gray-300">{row.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Advanced Configuration</h3>
      <p>For complex projects with custom requirements:</p>
      
      <CodeBlock language="yaml">
{`name: Advanced 0Pirate Analysis

on: [pull_request]

jobs:
  security-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Security Audit
        uses: 0pirate/analysis-action@v2
        with:
          api_key: \${{ secrets.ZERO_PIRATE_API_KEY }}
          task: 'security'
          provider: 'gpt-4'
          fail_on_issues: 'high'
          include_comments: true
          exclude_patterns: '**/test/**,**/node_modules/**,*.md'
          max_issues: 100
          timeout: 300
        env:
          GITHUB_TOKEN: \${{ secrets.GITHUB_TOKEN }}

  code-quality:
    runs-on: ubuntu-latest
    needs: security-audit
    steps:
      - uses: actions/checkout@v4
      
      - name: Code Quality Review
        uses: 0pirate/analysis-action@v2
        with:
          api_key: \${{ secrets.ZERO_PIRATE_API_KEY }}
          task: 'review'
          provider: 'gemini'
          fail_on_issues: 'medium'
          include_comments: true`}
      </CodeBlock>

      <h3>Example Output</h3>
      <p>The action provides detailed feedback in your workflow and can comment on pull requests:</p>
      
      <CodeBlock language="bash">
{`## 0Pirate Analysis Results

🔍 **Security Issues Found:** 2
⚠️ **Code Quality Issues:** 8
💡 **Suggestions:** 12

### Critical Security Issues:
1. **SQL Injection Vulnerability** (app/models/user.rb:45)
   - Risk: High
   - Fix: Use parameterized queries
   - Confidence: 96%

2. **Hardcoded API Key** (config/secrets.rb:23)  
   - Risk: High
   - Fix: Move to environment variables
   - Confidence: 98%

### Workflow Status: ❌ Failed (Critical issues found)
Analysis completed in 45.2s using gemini-pro`}
      </CodeBlock>

      <Callout type="success" title="Best Practice">
        <p>Use the GitHub Action in combination with other quality tools. Run security audits on every PR and comprehensive code reviews on main branch pushes.</p>
      </Callout>
    </div>
  </section>
);

const LLMPerspective = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="llm-perspective" ref={el => setRef('llm-perspective', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><Bot size={30} className="text-cyan-400" />LLM Perspective & Capabilities</h2>
      
      <div className="bg-gradient-to-r from-cyan-900/20 to-blue-900/20 p-6 rounded-xl border border-cyan-500/30 my-6">
        <h3 className="text-xl font-semibold text-white mb-4">What AI Models Actually See</h3>
        <p className="text-gray-300">
          Unlike traditional AI tools that send raw source code, 0Pirate transforms your code into <strong>secure abstract representations</strong> that preserve logic while removing sensitive information. This ensures your intellectual property remains protected.
        </p>
      </div>

      <h3>Code Transformation Process</h3>
      <p>Here's how your code is transformed for AI processing:</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">
        <div>
          <h4 className="font-semibold text-white mb-3">Original Code</h4>
          <CodeBlock language="python" showLineNumbers={true}>
{`import os
import requests

def fetch_user_data(user_id):
    api_key = os.environ.get('STRIPE_SECRET_KEY')
    response = requests.get(
        f"https://api.stripe.com/v1/users/{user_id}",
        headers={'Authorization': f'Bearer {api_key}'}
    )
    
    user_data = response.json()
    email = user_data.get('email')
    name = user_data.get('name')
    
    # Process sensitive business logic
    if email.endswith('@company.com'):
        apply_discount(user_data, 'EMPLOYEE_DISCOUNT')
    
    return user_data`}
          </CodeBlock>
        </div>
        
        <div>
          <h4 className="font-semibold text-white mb-3">What AI Sees</h4>
          <CodeBlock language="python" showLineNumbers={true}>
{`def fetch_user_data(user_id):
    api_key = "[REDACTED_CREDENTIAL]"
    response = "[API_CALL: stripe.com]"
    
    user_data = "[USER_DATA_OBJECT]"
    email = "[EMAIL_VALUE]"
    name = "[NAME_VALUE]"
    
    # Process sensitive business logic
    if email.endswith('@company.com'):
        "[BUSINESS_LOGIC: apply_discount]"
    
    return user_data`}
          </CodeBlock>
        </div>
      </div>

      <h3>Preserved Information</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">
        <div className="space-y-4">
          <h4 className="font-semibold text-green-400">✅ Preserved Elements</h4>
          {[
            "Code structure and flow",
            "Function and variable names",
            "Control structures (if/else, loops)",
            "Error handling patterns", 
            "Code comments and documentation",
            "Architectural patterns",
            "Dependencies and imports",
            "Method signatures"
          ].map((item, index) => (
            <div key={item} className="flex items-center gap-3">
              <CheckCircle size={16} className="text-green-400 flex-shrink-0" />
              <span className="text-gray-300 text-sm">{item}</span>
            </div>
          ))}
        </div>
        
        <div className="space-y-4">
          <h4 className="font-semibold text-red-400">❌ Abstracted Elements</h4>
          {[
            "API keys and credentials",
            "Database connection strings",
            "Personal identifiable information",
            "Business-specific algorithms",
            "Proprietary logic implementations", 
            "Encryption keys and salts",
            "Internal API endpoints",
            "Sensitive configuration values"
          ].map((item, index) => (
            <div key={item} className="flex items-center gap-3">
              <AlertTriangle size={16} className="text-red-400 flex-shrink-0" />
              <span className="text-gray-300 text-sm">{item}</span>
            </div>
          ))}
        </div>
      </div>

      <h3>AI Model Capabilities</h3>
      <p>Despite abstraction, AI models can still provide comprehensive analysis:</p>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-6">
        {[
          {
            capability: "Security Analysis",
            description: "Detect vulnerabilities, misconfigurations, and security anti-patterns",
            effectiveness: "95%"
          },
          {
            capability: "Code Quality",
            description: "Identify code smells, complexity issues, and maintainability problems", 
            effectiveness: "92%"
          },
          {
            capability: "Performance Optimization",
            description: "Suggest performance improvements and resource usage optimizations",
            effectiveness: "88%"
          },
          {
            capability: "Bug Detection", 
            description: "Find logical errors, edge cases, and potential runtime issues",
            effectiveness: "90%"
          },
          {
            capability: "Best Practices",
            description: "Recommend language-specific and framework-specific best practices",
            effectiveness: "94%"
          },
          {
            capability: "Architecture Review",
            description: "Analyze design patterns, coupling, and architectural decisions",
            effectiveness: "85%"
          }
        ].map((item, index) => (
          <motion.div 
            key={item.capability}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="p-4 rounded-lg bg-gray-800/50 border border-gray-700"
          >
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-white text-sm">{item.capability}</h4>
              <span className="text-green-400 text-xs font-semibold">{item.effectiveness}</span>
            </div>
            <p className="text-gray-400 text-xs">{item.description}</p>
          </motion.div>
        ))}
      </div>

      <Callout type="info" title="Context Preservation">
        <p>0Pirate's abstraction maintains the semantic meaning and context of your code. AI models receive enough information to understand what your code does without exposing how it does it or any sensitive implementation details.</p>
      </Callout>
    </div>
  </section>
);

const ApiKeys = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="api-keys" ref={el => setRef('api-keys', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><KeyRound size={30} className="text-yellow-400" />API Keys & Authentication</h2>
      
      <p>Secure API keys are required to access 0Pirate services. Manage your keys through the dashboard or programmatically via the API.</p>

      <h3>Creating API Keys</h3>
      <p>Generate new API keys from your account dashboard:</p>
      
      <ol>
        <li>Navigate to <strong>Account Settings</strong> → <strong>API Keys</strong></li>
        <li>Click <strong>"Generate New Key"</strong></li>
        <li>Provide a descriptive name for the key</li>
        <li>Set appropriate permissions and rate limits</li>
        <li>Copy the key immediately - it won't be shown again</li>
      </ol>

      <Callout type="warning" title="Security First">
        <p>API keys provide full access to your account. Store them securely and never commit them to version control. Use environment variables or secret management systems.</p>
      </Callout>

      <h3>Key Permissions</h3>
      <p>Fine-grained permissions control what each key can access:</p>
      
      <div className="overflow-x-auto my-6">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Permission</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Description</th>
              <th className="text-left py-3 px-4 text-gray-400 font-semibold">Default</th>
            </tr>
          </thead>
          <tbody>
            {[
              { permission: "analysis:read", description: "Read analysis results", default: "Yes" },
              { permission: "analysis:write", description: "Create new analyses", default: "Yes" },
              { permission: "keys:read", description: "View API key information", default: "No" },
              { permission: "keys:write", description: "Create and manage API keys", default: "No" },
              { permission: "billing:read", description: "View billing information", default: "No" },
              { permission: "admin", description: "Full administrative access", default: "No" }
            ].map((row, index) => (
              <tr key={row.permission} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="py-3 px-4 font-mono text-purple-400 text-sm">{row.permission}</td>
                <td className="py-3 px-4 text-gray-300">{row.description}</td>
                <td className="py-3 px-4 text-gray-300">{row.default}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Usage Examples</h3>
      <p>Here's how to use API keys in different environments:</p>

      <div className="space-y-6">
        <div>
          <h4 className="font-semibold text-white mb-2">Node.js / JavaScript</h4>
          <CodeBlock language="javascript">
{`const ZERO_PIRATE_API_KEY = process.env.ZERO_PIRATE_API_KEY;

async function analyzeCode(code, task = 'review') {
  const response = await fetch('https://api.0pirate.com/v1/analyze', {
    method: 'POST',
    headers: {
      'Authorization': \`Bearer \${ZERO_PIRATE_API_KEY}\`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      code: code,
      task: task,
      provider: 'gemini'
    })
  });
  
  return await response.json();
}`}
          </CodeBlock>
        </div>

        <div>
          <h4 className="font-semibold text-white mb-2">Python</h4>
          <CodeBlock language="python">
{`import os
import requests

ZERO_PIRATE_API_KEY = os.environ.get('ZERO_PIRATE_API_KEY')

def analyze_code(code, task='review'):
    response = requests.post(
        'https://api.0pirate.com/v1/analyze',
        headers={
            'Authorization': f'Bearer {ZERO_PIRATE_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'code': code,
            'task': task,
            'provider': 'gemini'
        }
    )
    return response.json()`}
          </CodeBlock>
        </div>

        <div>
          <h4 className="font-semibold text-white mb-2">GitHub Actions</h4>
          <CodeBlock language="yaml">
{`name: Secure Code Analysis
on: [push, pull_request]

env:
  ZERO_PIRATE_API_KEY: \${{ secrets.ZERO_PIRATE_API_KEY }}

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Analyze with 0Pirate
        run: |
          curl -X POST https://api.0pirate.com/v1/analyze \\
            -H "Authorization: Bearer \$ZERO_PIRATE_API_KEY" \\
            -H "Content-Type: application/json" \\
            -d '{"code": "$(cat src/main.py)", "task": "security"}'`}
          </CodeBlock>
        </div>
      </div>

      <h3>Rate Limiting</h3>
      <p>API requests are subject to rate limits based on your plan:</p>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 my-6 text-center">
        {[
          { plan: "Free", requests: "100", period: "per day" },
          { plan: "Pro", requests: "10,000", period: "per month" },
          { plan: "Team", requests: "50,000", period: "per month" },
          { plan: "Enterprise", requests: "Unlimited", period: "custom" }
        ].map((limit, index) => (
          <div key={limit.plan} className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
            <h4 className="font-semibold text-white">{limit.plan}</h4>
            <div className="text-2xl font-bold text-blue-400 my-2">{limit.requests}</div>
            <div className="text-gray-400 text-sm">{limit.period}</div>
          </div>
        ))}
      </div>

      <Callout type="tip" title="Monitoring Usage">
        <p>Track your API usage in the dashboard to avoid hitting limits. Set up alerts for high usage and consider upgrading your plan if you consistently approach your limits.</p>
      </Callout>
    </div>
  </section>
);

const BestPractices = ({ setRef }: { setRef: (id: string, el: HTMLElement | null) => void }) => (
  <section id="best-practices" ref={el => setRef('best-practices', el)} className="mb-16 scroll-mt-20">
    <div className="prose-doc">
      <h2><CheckCircle size={30} className="text-green-400" />Best Practices</h2>
      
      <p>Follow these guidelines to get the most value from 0Pirate while maintaining security and efficiency.</p>

      <h3>Code Preparation</h3>
      <div className="space-y-4 my-6">
        {[
          {
            practice: "Provide Context",
            description: "Include error messages, stack traces, or specific requirements to help AI understand the problem",
            example: "Instead of just code, add: 'This function fails when user input contains special characters'"
          },
          {
            practice: "Isolate the Issue", 
            description: "Extract relevant code sections rather than sending entire files when possible",
            example: "Focus on the specific function or class causing issues"
          },
          {
            practice: "Include Dependencies",
            description: "When analyzing complex code, include relevant imports and dependent function signatures",
            example: "Include interface definitions and key dependencies"
          },
          {
            practice: "Use Descriptive Names",
            description: "Well-named variables and functions help AI understand code intent",
            example: "prefer calculateTotalPrice over calcTP"
          }
        ].map((item, index) => (
          <motion.div 
            key={item.practice}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="p-4 rounded-lg bg-gray-800/50 border border-gray-700"
          >
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-xs font-bold">{index + 1}</span>
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-white text-sm">{item.practice}</h4>
                <p className="text-gray-400 text-sm mt-1">{item.description}</p>
                <div className="mt-2 p-2 bg-gray-900 rounded text-xs text-gray-300">
                  <strong>Example:</strong> {item.example}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <h3>Security Considerations</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">
        <div className="space-y-4">
          <h4 className="font-semibold text-green-400">✅ Do</h4>
          {[
            "Use environment variables for secrets",
            "Follow principle of least privilege for API keys",
            "Regularly rotate API keys and credentials",
            "Monitor usage patterns for anomalies",
            "Use separate keys for different environments"
          ].map((item, index) => (
            <div key={item} className="flex items-center gap-3">
              <CheckCircle size={16} className="text-green-400 flex-shrink-0" />
              <span className="text-gray-300 text-sm">{item}</span>
            </div>
          ))}
        </div>
        
        <div className="space-y-4">
          <h4 className="font-semibold text-red-400">❌ Don't</h4>
          {[
            "Commit API keys to version control",
            "Use production keys in development",
            "Share keys across team members",
            "Ignore security warnings from analysis",
            "Use overly permissive key permissions"
          ].map((item, index) => (
            <div key={item} className="flex items-center gap-3">
              <AlertTriangle size={16} className="text-red-400 flex-shrink-0" />
              <span className="text-gray-300 text-sm">{item}</span>
            </div>
          ))}
        </div>
      </div>

      <h3>Integration Strategies</h3>
      <div className="space-y-6 my-8">
        {[
          {
            strategy: "Progressive Integration",
            steps: [
              "Start with manual code reviews in the web app",
              "Add to CI/CD for critical security checks",
              "Expand to comprehensive code quality analysis",
              "Integrate with team workflows and PR processes"
            ]
          },
          {
            strategy: "Team Adoption",
            steps: [
              "Train team members on effective prompt engineering",
              "Establish guidelines for when to use AI assistance",
              "Create shared context and knowledge base",
              "Monitor and share successful use cases"
            ]
          },
          {
            strategy: "Scaling Usage", 
            steps: [
              "Monitor API usage and plan upgrades proactively",
              "Use webhooks for asynchronous processing",
              "Implement caching for repeated analyses",
              "Set up alerts for unusual patterns or limits"
            ]
          }
        ].map((strategy, index) => (
          <motion.div 
            key={strategy.strategy}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.2 }}
            className="p-5 rounded-xl border border-gray-700 bg-gray-900/30"
          >
            <h4 className="font-semibold text-white mb-3">{strategy.strategy}</h4>
            <ol className="space-y-2">
              {strategy.steps.map((step, stepIndex) => (
                <li key={stepIndex} className="flex items-start gap-3 text-sm text-gray-300">
                  <span className="w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 text-xs text-white">
                    {stepIndex + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </motion.div>
        ))}
      </div>

      <h3>Performance Optimization</h3>
      <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 p-5 rounded-xl border border-blue-500/30 my-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-semibold text-white mb-3">For Faster Results</h4>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• Use Gemini Pro for most code analysis tasks</li>
              <li>• Break large codebases into logical chunks</li>
              <li>• Cache analysis results when appropriate</li>
              <li>• Use webhooks for non-blocking processing</li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3">For Complex Problems</h4>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• Use GPT-4 for complex reasoning tasks</li>
              <li>• Provide comprehensive context and examples</li>
              <li>• Use multiple analysis passes for validation</li>
              <li>• Combine with traditional testing approaches</li>
            </ul>
          </div>
        </div>
      </div>

      <Callout type="info" title="Continuous Improvement">
        <p>0Pirate continuously improves its abstraction techniques and AI model integrations. Stay updated with new features and best practices by following our changelog and documentation updates.</p>
      </Callout>
    </div>
  </section>
);

// --- Main Documentation Component ---

export default function Documentation() {
  const [activeTab, setActiveTab] = useState<'user' | 'dev'>('user');
  const [searchQuery, setSearchQuery] = useState('');
  const [isDocsOpen, setIsDocsOpen] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLElement>>({});

  const setRef = useCallback((id: string, el: HTMLElement | null) => {
    if (el) {
      sectionRefs.current[id] = el;
    }
  }, []);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    // In a real implementation, you would filter content based on the query
  }, []);

  if (!isDocsOpen) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white">
        <div className="container mx-auto px-4 py-16">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-6xl mx-auto text-center"
          >
            <div className="flex justify-center mb-8">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center">
                <Lock size={32} />
              </div>
            </div>
            
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
              0Pirate Docs
            </h1>
            
            <p className="text-xl md:text-2xl text-gray-400 mb-12 max-w-3xl mx-auto leading-relaxed">
              Enterprise-grade AI code analysis with <span className="text-green-400 font-semibold">Zero-Trust security</span>. 
              Protect your IP while leveraging advanced AI capabilities.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto mb-16">
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-8 border border-gray-700 hover:border-blue-500 transition-all duration-300 cursor-pointer"
                onClick={() => {
                  setActiveTab('user');
                  setIsDocsOpen(true);
                }}
              >
                <div className="w-12 h-12 bg-blue-500 rounded-xl flex items-center justify-center mb-4 mx-auto">
                  <Users size={24} />
                </div>
                <h3 className="text-2xl font-bold text-white mb-3">User Guide</h3>
                <p className="text-gray-400 mb-4">
                  Get started with the web app, learn security features, and master code analysis workflows.
                </p>
                <div className="flex items-center justify-center text-blue-400 font-semibold">
                  Start Learning <ChevronRight size={16} className="ml-1" />
                </div>
              </motion.div>

              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-8 border border-gray-700 hover:border-purple-500 transition-all duration-300 cursor-pointer"
                onClick={() => {
                  setActiveTab('dev');
                  setIsDocsOpen(true);
                }}
              >
                <div className="w-12 h-12 bg-purple-500 rounded-xl flex items-center justify-center mb-4 mx-auto">
                  <Code size={24} />
                </div>
                <h3 className="text-2xl font-bold text-white mb-3">Developer Guide</h3>
                <p className="text-gray-400 mb-4">
                  API reference, GitHub Action, integration guides, and advanced implementation details.
                </p>
                <div className="flex items-center justify-center text-purple-400 font-semibold">
                  Explore API <ChevronRight size={16} className="ml-1" />
                </div>
              </motion.div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {[
                { icon: Shield, title: "Zero-Trust Security", desc: "Your code never leaves your control" },
                { icon: Cpu, title: "Multi-Model AI", desc: "Gemini, GPT, Claude, Ollama & more" },
                { icon: Zap, title: "Enterprise Ready", desc: "CI/CD, teams, and scalability" }
              ].map((feature, index) => (
                <motion.div 
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.2 }}
                  className="text-center p-4"
                >
                  <feature.icon size={32} className="mx-auto mb-3 text-blue-400" />
                  <h4 className="font-semibold text-white mb-2">{feature.title}</h4>
                  <p className="text-gray-400 text-sm">{feature.desc}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <DocsLayout 
      activeTab={activeTab} 
      onBack={() => setIsDocsOpen(false)}
      searchQuery={searchQuery}
      onSearchChange={handleSearch}
    >
      {(refs) => (
        <>
          {activeTab === 'user' ? (
            <>
              <Introduction setRef={setRef} />
              <QuickStart setRef={setRef} />
              <WebAppUsage setRef={setRef} />
              <SecurityModel setRef={setRef} />
              <SupportedModels setRef={setRef} />
              <UseCases setRef={setRef} />
              <Support setRef={setRef} />
            </>
          ) : (
            <>
              <Introduction setRef={setRef} />
              <ApiReference setRef={setRef} />
              <GitHubAction setRef={setRef} />
              <LLMPerspective setRef={setRef} />
              <SecurityModel setRef={setRef} />
              <SupportedModels setRef={setRef} />
              <ApiKeys setRef={setRef} />
              <BestPractices setRef={setRef} />
            </>
          )}
        </>
      )}
    </DocsLayout>
  );
}