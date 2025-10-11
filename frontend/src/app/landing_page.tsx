"use client";

import React, { useRef, useEffect, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { 
  ArrowRight, 
  Bot,
  Mail,
  Linkedin,
  MessageSquare
} from "lucide-react";

// --- SEO Helper: JSON-LD Schema Markup ---
function SchemaMarkup() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "0Pirate (Zero Pirate)",
    "description": "The Zero-Trust AI Gateway for Enterprise Code. A secure platform that uses AST-Abstraction to protect intellectual property while accelerating code security, bug fixes, and refactoring with powerful Large Language Models (LLMs).",
    "url": "https://www.0pirate.com", // Replace with your domain
    "applicationCategory": "DeveloperTool",
    "operatingSystem": "All (Web SaaS)",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    },
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.9", // High rating for social proof
      "ratingCount": "120"
    }
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

// --- Interactive Background Component ---
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

// --- Interactive Bot Icon with Eye Tracking ---
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
      const width = rect.width;
      const height = rect.height;
      const mouseX_relative = e.clientX - rect.left;
      const mouseY_relative = e.clientY - rect.top;
      
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

// --- Main Landing Page Component ---
export default function LandingPage({ onNavigate }: { onNavigate: () => void }) {
  const [showContact, setShowContact] = useState(false);
  
  const styles = `
    :root {
      --text-primary: #EAEAEA;
      --text-secondary: #A0A0A0;
      --accent-primary: #3B82F6;
      --accent-primary-hover: #2563EB;
      --border-primary: rgba(255, 255, 255, 0.1);
    }
    .lp-container { 
      width: 100%; 
      height: 100vh; 
      position: relative; 
      overflow: hidden;
    }
    .lp-container::before {
      content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: radial-gradient(circle 600px at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(74, 144, 226, 0.15), transparent 80%);
      pointer-events: none;
    }
    /* This hero container uses flexbox to perfectly center its content */
    .lp-hero { 
      width: 100%; 
      height: 100%;
      display: flex; 
      align-items: center; 
      justify-content: center; 
      padding: 0 1.5rem; 
      position: relative; 
      z-index: 2;
    }
    .lp-hero-content-stack {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .lp-hero-icon { 
      display: inline-flex; align-items: center; justify-content: center; 
      width: 80px; height: 80px;
      border-radius: 50%; background-color: rgba(74, 144, 226, 0.1); 
      border: 1px solid var(--border-primary); color: var(--accent-primary); 
    }
    .lp-title { 
      font-size: clamp(3rem, 7vw, 5.5rem); font-weight: 700; 
      letter-spacing: -0.04em; line-height: 1.1;
      margin-bottom: 1.5rem; color: var(--text-primary); 
    }
    .lp-title-gradient { 
      display: block; background: linear-gradient(90deg, var(--accent-primary), #8a5cf6); 
      -webkit-background-clip: text; background-clip: text; 
      -webkit-text-fill-color: transparent; color: transparent; 
    }
    .lp-subtitle { 
      max-width: 720px; font-size: clamp(1rem, 2vw, 1.25rem); 
      color: var(--text-secondary); line-height: 1.7;
      margin-bottom: 2.5rem; 
    }
    .lp-cta-btn { 
      display: inline-flex; align-items: center; justify-content: center; 
      gap: 0.75rem; font-size: 1.1rem; font-weight: 500; 
      padding: 1rem 2rem; border-radius: 9999px; 
      color: white; background-color: var(--accent-primary); 
      border: none; transition: all 0.2s ease; cursor: pointer; 
    }
    .lp-cta-btn:hover { 
      background-color: var(--accent-primary-hover); 
      transform: translateY(-2px); box-shadow: 0 4px 20px rgba(74, 144, 226, 0.3); 
    }
    .lp-footer {
      position: absolute; bottom: 0; left: 0; right: 0;
      padding: 1.5rem; text-align: center; color: var(--text-secondary);
      font-size: 0.875rem; z-index: 2;
    }
    .fixed-contact-btn {
      position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 100;
      width: 56px; height: 56px; background-color: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      cursor: pointer; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      transition: transform 0.2s ease, background-color 0.2s ease;
    }
    .fixed-contact-btn:hover {
      background-color: rgba(255, 255, 255, 0.2); transform: scale(1.1);
    }
    .fixed-contact-btn .icon { color: var(--text-primary); width: 28px; height: 28px; }
    .contact-popup { position: fixed; bottom: 80px; right: 1.5rem; z-index: 101; background-color: rgba(30,30,30,0.8); backdrop-filter: blur(10px); border: 1px solid var(--border-primary); border-radius: 12px; padding: 1.5rem; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5); min-width: 250px; opacity: 0; visibility: hidden; transform: translateY(20px); transition: opacity 0.3s ease, visibility 0.3s ease, transform 0.3s ease; }
    .contact-popup.visible { opacity: 1; visibility: visible; transform: translateY(0); }
    .contact-popup-item { display: flex; align-items: center; gap: 0.75rem; color: var(--text-secondary); transition: color 0.2s ease; }
    .contact-popup-item:hover { color: var(--accent-primary); }
    .contact-popup-item + .contact-popup-item { margin-top: 0.75rem; }
    .contact-popup-title { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1rem; }
  `;

  return (
    <>
      <InteractiveBackground />
      <style>{styles}</style>
      
      <div className="lp-container">
        <main className="lp-hero">
          
          <motion.div
            className="lp-hero-content-stack"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={fadeInUp}>
              <InteractiveBotIcon />
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

        </main>

        <div className="fixed-contact-btn" onClick={() => setShowContact(!showContact)}>
          <MessageSquare className="icon" />
        </div>

        <div className={`contact-popup ${showContact ? 'visible' : ''}`}>
          <div className="contact-popup-title">Get in Touch</div>
          <a href="mailto:support@0pirate.com" className="contact-popup-item">
            <Mail className="w-5 h-5" />
            <span>support@0pirate.com</span>
          </a>
          <a href="https://www.linkedin.com/company/0pirateorg" target="_blank" rel="noopener noreferrer" className="contact-popup-item">
            <Linkedin className="w-5 h-5" />
            <span>LinkedIn Company Page</span>
          </a>
        </div>
        
        <footer className="lp-footer">
          <p>&copy; {new Date().getFullYear()} 0PIRATE. All rights reserved.</p>
        </footer>
      </div>
    </>
  );
}