import React, { useState, useEffect } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { ChevronLeft, Book, Shield, Cpu, Lock, Zap, Server, Terminal } from 'lucide-react';
import { modelsDocs } from '../data/modelsDocs';

// Custom components for markdown rendering
const MarkdownComponents = {
    h1: ({ node, ...props }: any) => (
        <motion.h1
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-4xl md:text-5xl font-bold mb-8 text-white"
            {...props}
        />
    ),
    h2: ({ node, ...props }: any) => (
        <motion.h2
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="text-2xl md:text-3xl font-semibold mt-12 mb-6 text-white flex items-center gap-3 border-b border-white/10 pb-2"
            {...props}
        />
    ),
    h3: ({ node, ...props }: any) => (
        <h3 className="text-xl font-medium mt-8 mb-4 text-blue-400" {...props} />
    ),
    p: ({ node, ...props }: any) => (
        <p className="text-gray-400 leading-relaxed mb-6 text-lg" {...props} />
    ),
    ul: ({ node, ...props }: any) => (
        <ul className="list-disc list-inside space-y-2 mb-6 text-gray-300 ml-4" {...props} />
    ),
    li: ({ node, ...props }: any) => (
        <li className="pl-2" {...props} />
    ),
    strong: ({ node, ...props }: any) => (
        <strong className="text-white font-semibold" {...props} />
    ),
    blockquote: ({ node, ...props }: any) => (
        <motion.blockquote
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            className="border-l-4 border-blue-500 pl-6 py-4 my-8 bg-blue-500/5 rounded-r-lg italic text-blue-200"
            {...props}
        />
    ),
    code: ({ node, inline, className, children, ...props }: any) => {
        return inline ? (
            <code className="bg-gray-800 text-blue-300 px-1.5 py-0.5 rounded font-mono text-sm" {...props}>
                {children}
            </code>
        ) : (
            <div className="relative group">
                <pre className="relative bg-[#0D0D0D] p-4 rounded-lg overflow-x-auto border border-white/10 text-gray-300 font-mono text-sm mb-6">
                    <code {...props}>{children}</code>
                </pre>
            </div>
        );
    }
};

export default function Documentation({ onBack }: { onBack: () => void }) {
    const [activeSection, setActiveSection] = useState('');
    const { scrollYProgress } = useScroll();
    const scaleX = useTransform(scrollYProgress, [0, 1], [0, 1]);

    useEffect(() => {
        const handleScroll = () => {
            const sections = document.querySelectorAll('h2');
            let current = '';
            sections.forEach((section) => {
                const sectionTop = section.offsetTop;
                if (window.scrollY >= sectionTop - 200) {
                    current = section.id;
                }
            });
            setActiveSection(current);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    // Pre-process markdown to add IDs to H2s for scrollspy
    const contentWithIds = modelsDocs.replace(
        /## (.*?)\n/g,
        (match, title) => `## <span id="${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}"></span>${title}\n`
    );

    return (
        <div className="min-h-screen bg-black text-white selection:bg-blue-500/30">
            {/* Progress Bar */}
            <motion.div
                className="fixed top-0 left-0 right-0 h-1 bg-blue-600 origin-left z-50"
                style={{ scaleX }}
            />

            {/* Navigation */}
            <header className="fixed top-0 w-full z-40 bg-black/80 backdrop-blur-md border-b border-white/5">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors group"
                    >
                        <ChevronLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
                        Back to App
                    </button>
                    <div className="flex items-center gap-2 font-semibold text-white">
                        <Book size={18} className="text-blue-500" />
                        Documentation
                    </div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-6 pt-32 pb-20 relative">
                {/* Hero Section of Docs */}
                <div className="mb-16 text-center">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.5 }}
                        className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-500/10 mb-6 text-blue-500"
                    >
                        <Shield size={32} />
                    </motion.div>
                    <h1 className="text-5xl font-bold text-white mb-6">
                        Secure AI Gateway
                    </h1>
                    <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                        Understand how 0Pirate protects your intellectual property while leveraging the world's best AI models.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
                    <div className="lg:col-span-12">
                        <ReactMarkdown components={MarkdownComponents}>
                            {contentWithIds}
                        </ReactMarkdown>
                    </div>
                </div>
            </main>
        </div>
    );
}
