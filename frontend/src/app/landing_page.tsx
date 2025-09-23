"use client";

import React, { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { 
  Shield, Lock, Code, ArrowRight, Eye, CheckCircle, Bot, AlertTriangle, KeyRound, 
  Workflow, Container, Zap, GitBranch, ChevronsRight
} from "lucide-react";

// --- Animation Variants ---
const fadeInUp = {
  initial: { opacity: 0, y: 50 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.2, 0.65, 0.3, 0.9] } }
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1
    }
  }
};

// --- Custom Code Block Component (No External Dependencies) ---
const CustomCodeBlock = ({ codeString }: { codeString: string }) => {
  return (
    <pre className="lp-code-block">
      <code>{codeString}</code>
    </pre>
  );
};

// --- Main Landing Page Component ---
export default function LandingPage({ onNavigate }: { onNavigate: () => void }) {
  const pageRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: pageRef,
    offset: ["start start", "end start"]
  });

  // Parallax transformations for the hero section
  const heroOpacity = useTransform(scrollYProgress, [0, 0.3], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.3], [1, 0.9]);
  const heroY = useTransform(scrollYProgress, [0, 0.3], [0, -150]);

  // --- Data for Sections ---
  const securityFeatures = [
    { icon: Shield, title: "Zero-Knowledge Architecture", description: "Your code and secrets never leave your secure environment." },
    { icon: KeyRound, title: "Bring Your Own Key (BYOK)", description: "Maintain full control over your LLM providers and credentials." },
    { icon: Lock, title: "Automated Secret Redaction", description: "Sensitive data is automatically found and replaced with secure placeholders." },
    { icon: Container, title: "Isolated Docker Sandbox", description: "AI-generated code is tested in a secure, air-gapped environment before delivery." }
  ];

  const keyFeatures = {
    security: [
      { icon: Shield, title: "Zero-Knowledge Architecture" },
      { icon: KeyRound, title: "Bring Your Own Key (BYOK) Model" },
      { icon: Lock, title: "Automated Secret Redaction" },
      { icon: AlertTriangle, title: "Static Vulnerability Scanning" },
      { icon: Container, title: "Isolated Docker Sandbox Execution" },
    ],
    intelligence: [
      { icon: Workflow, title: "Advanced HAIS Pipeline" },
      { icon: ChevronsRight, title: "Provider-Agnostic Routing" },
      { icon: Zap, title: "Asynchronous API for CI/CD" },
      { icon: GitBranch, title: "Resilient LLM Interaction" },
    ],
    developerExperience: [
      { icon: Code, title: "Simple CLI for Local Use" },
      { icon: Eye, title: "Optional Diff Output (Token Saver)" },
      { icon: Zap, title: "Multi-Language Support" },
      { icon: Code, title: "Scalable API Server for Teams" },
    ]
  };

  const codeSnippets = {
    before: `import requests
API_KEY = "sk-secret-xxxxx"

def get_user_data(user_id):
    # SQL injection vulnerability
    db_query = "SELECT * FROM users WHERE id = " + user_id
    response = requests.get(f"https://api.internal/users/{user_id}")
    return response.json()`,
    after: `import requests
import sqlite3

# API_KEY is securely restored from the vault post-analysis
API_KEY = "sk-secret-xxxxx"

def get_user_data(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Parameterized query prevents SQL injection
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    
    try:
        # Added timeout and error handling for robustness
        response = requests.get(
            f"https://api.internal/users/{user_id}", 
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API error: {e}")
        return None`
  };
  
  const styles = `
    /* The body itself gets the grid pattern from globals.css */
    .lp-container { width: 100%; position: relative; }
    /* The gradient is now part of the main container, not fixed */
    .lp-container::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 100vh;
      background: radial-gradient(ellipse 60% 80% at 50% -20%, rgba(74, 144, 226, 0.15), transparent 70%);
      z-index: 0;
    }
    .lp-hero { height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; padding: 0 1.5rem; position: sticky; top: 0; z-index: 1; }
    .lp-hero-icon { display: inline-flex; align-items: center; justify-content: center; padding: 1rem; border-radius: 50%; background-color: rgba(74, 144, 226, 0.1); border: 1px solid var(--border-primary); color: var(--accent-primary); }
    .lp-title { font-size: clamp(3rem, 7vw, 5.5rem); font-weight: 700; letter-spacing: -0.04em; line-height: 1.1; text-align: center; margin-bottom: 1.5rem; color: var(--text-primary); }
    .lp-title-gradient { display: block; background: linear-gradient(90deg, var(--accent-primary), #8a5cf6); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; }
    .lp-subtitle { max-width: 720px; font-size: clamp(1rem, 2vw, 1.25rem); color: var(--text-secondary); line-height: 1.7; text-align: center; margin-bottom: 2.5rem; }
    .lp-cta-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.75rem; font-size: 1.1rem; font-weight: 500; padding: 1rem 2rem; border-radius: 9999px; color: white; background-color: var(--accent-primary); border: none; transition: all 0.2s ease; cursor: pointer; }
    .lp-cta-btn:hover { background-color: var(--accent-primary-hover); transform: translateY(-2px); box-shadow: 0 4px 20px rgba(74, 144, 226, 0.3); }
    .lp-main-content { position: relative; z-index: 10; background-color: var(--background-deep); }
    .lp-section { max-width: 1200px; margin: 0 auto; padding: 8rem 1.5rem; }
    .lp-section-title { font-size: clamp(2.5rem, 5vw, 3.5rem); font-weight: 700; letter-spacing: -0.03em; color: var(--text-primary); text-align: center; }
    .lp-section-subtitle { font-size: 1.2rem; color: var(--text-secondary); max-width: 700px; margin: 1rem auto 0; text-align: center; line-height: 1.7; }
    .lp-features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; }
    .lp-feature-card { border-radius: 20px; background: linear-gradient(145deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)); padding: 1px; transition: transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.4s cubic-bezier(0.2, 0.8, 0.2, 1); transform-style: preserve-3d; }
    .lp-feature-card:hover { transform: perspective(1500px) rotateX(8deg) rotateY(-6deg) scale(1.05); box-shadow: 0px 20px 40px rgba(0, 0, 0, 0.3); }
    .lp-feature-card-content { background: var(--background-light); border-radius: 19px; padding: 2.5rem; height: 100%; text-align: left; border: 1px solid var(--border-secondary); }
    .lp-feature-icon { display: inline-flex; padding: 1rem; border-radius: 16px; background-color: var(--accent-primary); color: white; margin-bottom: 1.5rem; }
    .lp-card-title { font-size: 1.25rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.75rem; }
    .lp-card-description { font-size: 1rem; color: var(--text-secondary); line-height: 1.6; }
    .lp-code-flow-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; align-items: stretch; }
    @media (min-width: 1024px) { .lp-code-flow-grid { grid-template-columns: 1fr auto 1fr; } }
    .lp-code-card { background-color: var(--code-editor); border: 1px solid var(--border-primary); border-radius: 12px; padding: 1.5rem; height: 100%; }
    .lp-code-title { display: block; font-size: 0.9rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 1rem; text-align: center; }
    .lp-key-features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 2rem; }
    .lp-key-feature-item { display: flex; align-items: center; gap: 1rem; background-color: var(--background-light); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-secondary); }
    .lp-cta-card { padding: 5rem 2rem; border-radius: 24px; background: var(--background-light); text-align: center; border: 1px solid var(--border-primary); background-image: radial-gradient(circle at center, rgba(74, 144, 226, 0.1), transparent 70%); }
    .lp-footer { text-align: center; padding: 4rem 1.5rem; border-top: 1px solid var(--border-primary); }
    .lp-code-block { background-color: transparent !important; font-family: var(--font-fira-code), monospace; color: #abb2bf; padding: 0; margin: 0; overflow: auto; border-radius: 8px; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; }
  `;

  return (
    <>
      <style>{styles}</style>
      
      <div ref={pageRef} className="lp-container">
        <motion.header 
          className="lp-hero"
          style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
        >
          <motion.div
            className="relative z-10 text-center flex flex-col items-center"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={fadeInUp} className="mb-6">
              <div className="lp-hero-icon"><Bot size={40} /></div>
            </motion.div>
            <motion.h1 className="lp-title" variants={fadeInUp}>
              Secure AI Gateway
              <span className="lp-title-gradient">for Enterprise Code</span>
            </motion.h1>
            <motion.p className="lp-subtitle" variants={fadeInUp}>
              Accelerate development with any LLM, while safeguarding your most valuable asset: your source code.
            </motion.p>
            <motion.div variants={fadeInUp}>
              <button onClick={onNavigate} className="lp-cta-btn group">
                Begin Your Voyage
                <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
              </button>
            </motion.div>
          </motion.div>
        </motion.header>

        <main className="lp-main-content">
          <motion.section className="lp-section" variants={staggerContainer} initial="initial" whileInView="animate" viewport={{ once: true, amount: 0.2 }}>
            <motion.div className="text-center mb-16" variants={fadeInUp}>
              <h2 className="lp-section-title">The Developer's Dilemma</h2>
              <p className="lp-section-subtitle">Organizations face conflicting priorities: the speed of AI versus the compliance of security. Naïve AI adoption risks IP loss, credential leakage, and regulatory violations.</p>
            </motion.div>
            <div className="lp-features-grid">
              {securityFeatures.map((feature, index) => (
                <motion.div key={index} className="lp-feature-card" variants={fadeInUp}>
                  <div className="lp-feature-card-content">
                    <div className="lp-feature-icon"><feature.icon className="w-6 h-6" /></div>
                    <h3 className="lp-card-title">{feature.title}</h3>
                    <p className="lp-card-description">{feature.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.section>

          <motion.section className="lp-section" initial="initial" whileInView="animate" viewport={{ once: true, amount: 0.2 }}>
            <motion.div className="text-center mb-16" variants={fadeInUp}>
              <h2 className="lp-section-title">From Vulnerable to Validated</h2>
              <p className="lp-section-subtitle">See our Zero-Knowledge workflow in action. We analyze, redact, fix, and restore your code without ever exposing your secrets to an LLM.</p>
            </motion.div>
            <div className="lp-code-flow-grid">
              <motion.div className="lp-code-card" variants={fadeInUp}>
                <span className="lp-code-title text-red-400">1. Vulnerable Code Submitted</span>
                <CustomCodeBlock codeString={codeSnippets.before} />
              </motion.div>
              <motion.div className="text-center" variants={fadeInUp}>
                <ArrowRight size={32} className="text-accent-primary my-4 lg:my-0 transform lg:rotate-0 rotate-90" />
              </motion.div>
              <motion.div className="lp-code-card" variants={fadeInUp}>
                <span className="lp-code-title text-green-400">2. Secure, Fixed Code Returned</span>
                <CustomCodeBlock codeString={codeSnippets.after} />
              </motion.div>
            </div>
          </motion.section>

          <motion.section className="lp-section" initial="initial" whileInView="animate" viewport={{ once: true, amount: 0.2 }}>
            <motion.div className="text-center mb-16" variants={fadeInUp}>
              <h2 className="lp-section-title">Key Features At-a-Glance</h2>
            </motion.div>
            <div className="lp-key-features-grid">
              <motion.div variants={fadeInUp}>
                <h3 className="text-2xl font-bold mb-6 text-left text-accent-primary">Security & Compliance</h3>
                <div className="space-y-4">
                  {keyFeatures.security.map((feat, i) => (
                    <div key={i} className="lp-key-feature-item"><feat.icon className="w-5 h-5 text-text-secondary flex-shrink-0" /><span>{feat.title}</span></div>
                  ))}
                </div>
              </motion.div>
              <motion.div variants={fadeInUp}>
                <h3 className="text-2xl font-bold mb-6 text-left text-accent-primary">Intelligence & Performance</h3>
                <div className="space-y-4">
                  {keyFeatures.intelligence.map((feat, i) => (
                    <div key={i} className="lp-key-feature-item"><feat.icon className="w-5 h-5 text-text-secondary flex-shrink-0" /><span>{feat.title}</span></div>
                  ))}
                </div>
              </motion.div>
              <motion.div variants={fadeInUp}>
                <h3 className="text-2xl font-bold mb-6 text-left text-accent-primary">Developer Experience</h3>
                <div className="space-y-4">
                  {keyFeatures.developerExperience.map((feat, i) => (
                    <div key={i} className="lp-key-feature-item"><feat.icon className="w-5 h-5 text-text-secondary flex-shrink-0" /><span>{feat.title}</span></div>
                  ))}
                </div>
              </motion.div>
            </div>
          </motion.section>

          <motion.section className="lp-section" initial="initial" whileInView="animate" viewport={{ once: true, amount: 0.3 }} variants={staggerContainer}>
            <div className="lp-cta-card">
              <motion.div variants={fadeInUp}>
                <h2 className="text-4xl md:text-5xl font-bold text-text-primary mb-4">Verifiable Security for AI</h2>
                <p className="text-xl text-text-secondary max-w-3xl mx-auto mb-8">
                  0PIRATE moves development from a model of blind trust to a model of verifiable security, empowering you to adopt any LLM with confidence.
                </p>
                <button onClick={onNavigate} className="lp-cta-btn group">
                  Start Your Free Trial
                  <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
                </button>
              </motion.div>
            </div>
          </motion.section>

          <footer className="lp-footer">
            <div className="flex items-center justify-center space-x-2 mb-4">
              <Bot className="text-accent-primary" size={24} />
              <span className="text-xl font-bold">0PIRATE</span>
            </div>
            <p className="text-text-secondary text-sm">
              &copy; {new Date().getFullYear()} 0PIRATE. All rights reserved.
            </p>
          </footer>
        </main>
      </div>
    </>
  );
}

