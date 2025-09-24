"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Star, Zap, Users, Building2 } from "lucide-react";

// Optimized cursor glow hook with performance improvements
const useCursorGlow = (ref: React.RefObject<HTMLElement>) => {
  const rafRef = useRef<number>();
  
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    
    rafRef.current = requestAnimationFrame(() => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        ref.current.style.setProperty('--mouse-x', `${x}px`);
        ref.current.style.setProperty('--mouse-y', `${y}px`);
      }
    });
  }, [ref]);

  const handleMouseLeave = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  return { onMouseMove: handleMouseMove, onMouseLeave: handleMouseLeave };
};

interface Plan {
  id: string;
  name: string;
  description: string;
  currency: 'INR' | 'USD';
  monthly: { price: number; razorpay_plan_id: string | null };
  yearly: { price: number; razorpay_plan_id: string | null };
  features: string[];
  icon?: React.ReactNode;
  popular?: boolean;
  highlight?: boolean;
}

interface PricingPageProps {
  onSelectFreePlan: () => void;
  onSelectPaidPlan: (planId: string, billingCycle: 'monthly' | 'yearly') => void;
}

export default function PricingPage({ onSelectFreePlan, onSelectPaidPlan }: PricingPageProps) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('yearly');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const developerCardRef = useRef<HTMLDivElement>(null);
  const glowEffect = useCursorGlow(developerCardRef);

  useEffect(() => {
    const fetchAndFormatPlans = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5001'}/api/plans`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        const enhancedPlans = (data.plans || []).map((plan: any) => {
          let updatedPlan = {...plan};
          
          switch(plan.id) {
            case 'free':
              updatedPlan.description = "Perfect for individuals and hobby projects";
              updatedPlan.features = [
                "2 Jobs per day",
                "5 Files per job", 
                "Core security features",
                "Access to all AI models",
                "Community support",
                "Basic code analysis"
              ];
              updatedPlan.icon = <Zap className="w-6 h-6" />;
              break;
              
            case 'developer':
              updatedPlan.description = "The complete toolkit for professional developers";
              updatedPlan.features = [
                "50 Jobs per day",
                "20 Files per job",
                "Advanced security scanning",
                "Priority AI model access",
                "CI/CD integration via API",
                "Email support",
                "Custom security rules",
                "Detailed reporting"
              ];
              updatedPlan.icon = <Star className="w-6 h-6" />;
              updatedPlan.popular = true;
              break;
              
            case 'professional':
              updatedPlan.description = "For growing teams that need to collaborate securely";
              updatedPlan.features = [
                "200 Jobs per day",
                "50 Files per job",
                "5 Team seats included",
                "Priority email & chat support",
                "Team management dashboard",
                "Advanced analytics",
                "Custom integrations",
                "All developer features"
              ];
              updatedPlan.icon = <Users className="w-6 h-6" />;
              updatedPlan.highlight = true;
              break;
          }
          return updatedPlan;
        });
        
        setPlans(enhancedPlans);
      } catch (err: any) {
        console.error("Failed to fetch pricing plans:", err);
        setError(err.message || "Failed to load pricing plans.");
      } finally {
        setLoading(false);
      }
    };

    fetchAndFormatPlans();
  }, []);

  const formatPrice = (price: number, currency: 'INR' | 'USD') => {
    const amount = price / 100;
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const enterprisePlan = {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Custom solutions for large organizations',
    features: [
      "Unlimited job quotas",
      "Dedicated account manager", 
      "99.9% uptime SLA",
      "SSO & audit logs",
      "Custom onboarding",
      "Priority phone support",
      "Advanced compliance tools",
      "Custom reporting"
    ],
    icon: <Building2 className="w-6 h-6" />
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-gray-400">
        <div className="relative">
          <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
        </div>
        <p className="mt-6 text-lg font-medium">Loading pricing plans...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-red-400">
        <p className="text-lg">Error loading plans: {error}</p>
      </div>
    );
  }

  const allPlans = [...plans, enterprisePlan];

  return (
    <div className="w-full min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-800 py-20 px-4">
      <style jsx>{`
        .pricing-container {
          max-width: 1400px;
          margin: 0 auto;
        }

        .pricing-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
          margin-top: 3rem;
        }

        @media (min-width: 640px) {
          .pricing-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 2rem;
          }
        }

        @media (min-width: 1024px) {
          .pricing-grid {
            grid-template-columns: repeat(4, 1fr);
          }
        }

        .plan-card {
          background: linear-gradient(145deg, #1a1a1a, #0f0f0f);
          border: 1px solid #333;
          border-radius: 24px;
          padding: 2rem;
          position: relative;
          transform-origin: center;
          will-change: transform, box-shadow;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
        }

        .plan-card:hover {
          transform: translateY(-8px) scale(1.02);
          box-shadow: 
            0 25px 50px -12px rgba(0, 0, 0, 0.8),
            0 0 0 1px rgba(255, 255, 255, 0.1);
          border-color: #555;
        }

        .developer-card {
          border: 2px solid #3b82f6;
          background: linear-gradient(145deg, #1e293b, #0f172a);
          position: relative;
        }

        .developer-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          border-radius: 24px;
          background: radial-gradient(
            circle 400px at var(--mouse-x, 50%) var(--mouse-y, 50%),
            rgba(59, 130, 246, 0.15) 0%,
            rgba(59, 130, 246, 0.08) 40%,
            transparent 70%
          );
          opacity: 0;
          transition: opacity 0.3s ease;
          pointer-events: none;
        }

        .developer-card:hover::before {
          opacity: 1;
        }

        .professional-card {
          border: 2px solid #10b981;
          background: linear-gradient(145deg, #064e3b, #022c22);
        }

        .toggle-container {
          background: rgba(31, 41, 55, 0.8);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(75, 85, 99, 0.3);
          border-radius: 50px;
          padding: 6px;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto;
          width: fit-content;
        }

        .toggle-button {
          padding: 12px 32px;
          font-weight: 600;
          font-size: 16px;
          border-radius: 50px;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
          z-index: 10;
          cursor: pointer;
          border: none;
          background: transparent;
        }

        .toggle-slider {
          position: absolute;
          top: 6px;
          bottom: 6px;
          width: calc(50% - 6px);
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          border-radius: 50px;
          transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 
            0 4px 14px 0 rgba(59, 130, 246, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
        }

        .feature-list {
          list-style: none;
          padding: 0;
          margin: 2rem 0;
          space-y: 1rem;
        }

        .feature-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 8px 0;
          border-bottom: 1px solid rgba(75, 85, 99, 0.2);
        }

        .feature-item:last-child {
          border-bottom: none;
        }

        .feature-icon {
          color: #10b981;
          flex-shrink: 0;
          margin-top: 2px;
        }

        .btn {
          width: 100%;
          padding: 16px 24px;
          border-radius: 12px;
          font-weight: 600;
          font-size: 16px;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          border: none;
          cursor: pointer;
          position: relative;
          overflow: hidden;
        }

        .btn-primary {
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          color: white;
          box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.4);
        }

        .btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px 0 rgba(59, 130, 246, 0.6);
        }

        .btn-secondary {
          background: linear-gradient(145deg, #374151, #1f2937);
          color: white;
          border: 1px solid #4b5563;
        }

        .btn-secondary:hover {
          transform: translateY(-2px);
          background: linear-gradient(145deg, #4b5563, #374151);
          box-shadow: 0 8px 25px 0 rgba(0, 0, 0, 0.3);
        }

        .popular-badge {
          position: absolute;
          top: -1px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          color: white;
          padding: 8px 24px;
          border-radius: 0 0 12px 12px;
          font-size: 14px;
          font-weight: 700;
          z-index: 20;
          box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.4);
        }

        .savings-badge {
          position: absolute;
          top: -12px;
          right: -12px;
          background: linear-gradient(135deg, #10b981, #059669);
          color: white;
          padding: 8px 16px;
          border-radius: 50px;
          font-size: 12px;
          font-weight: 700;
          transform: rotate(12deg);
          z-index: 30;
          box-shadow: 0 4px 14px 0 rgba(16, 185, 129, 0.4);
        }
      `}</style>

      <div className="pricing-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center"
        >
          <h1 className="text-5xl md:text-7xl font-bold bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent mb-6">
            Plans & Pricing
          </h1>
          <p className="text-xl md:text-2xl text-gray-400 max-w-3xl mx-auto leading-relaxed">
            Start for free, then scale up with higher limits and advanced team features
          </p>
        </motion.div>

        {/* Billing Toggle */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="flex justify-center mt-12 relative"
        >
          <div className="toggle-container">
            <button
              onClick={() => setBillingCycle('monthly')}
              className="toggle-button"
              style={{ 
                color: billingCycle === 'monthly' ? 'white' : '#9ca3af',
              }}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className="toggle-button"
              style={{ 
                color: billingCycle === 'yearly' ? 'white' : '#9ca3af',
              }}
            >
              Yearly
            </button>
            <motion.div
              className="toggle-slider"
              animate={{
                transform: billingCycle === 'monthly' 
                  ? 'translateX(0%)' 
                  : 'translateX(100%)'
              }}
              transition={{
                type: 'spring',
                stiffness: 400,
                damping: 30
              }}
            />
            <AnimatePresence>
              {billingCycle === 'yearly' && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8, rotate: -10 }}
                  animate={{ opacity: 1, scale: 1, rotate: 12 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="savings-badge"
                >
                  Save 17%
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Pricing Cards */}
        <div className="pricing-grid">
          {allPlans.map((plan: any, index) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ 
                delay: 0.5 + index * 0.1, 
                duration: 0.6,
                ease: "easeOut"
              }}
              className={`plan-card ${
                plan.id === 'developer' ? 'developer-card' : ''
              } ${
                plan.highlight ? 'professional-card' : ''
              }`}
              ref={plan.id === 'developer' ? developerCardRef : null}
              {...(plan.id === 'developer' ? glowEffect : {})}
            >
              {plan.popular && (
                <div className="popular-badge">
                  Most Popular
                </div>
              )}

              <div className="flex items-center gap-3 mb-4">
                <div className={`p-3 rounded-xl ${
                  plan.id === 'developer' ? 'bg-blue-500/20 text-blue-400' :
                  plan.highlight ? 'bg-emerald-500/20 text-emerald-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {plan.icon}
                </div>
                <div>
                  <h3 className={`text-2xl font-bold ${
                    plan.id === 'developer' ? 'text-blue-400' :
                    plan.highlight ? 'text-emerald-400' :
                    'text-white'
                  }`}>
                    {plan.name}
                  </h3>
                </div>
              </div>

              <p className="text-gray-400 mb-8 text-lg leading-relaxed">
                {plan.description}
              </p>

              <div className="mb-8">
                {plan.id === 'enterprise' ? (
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-bold text-white">Custom</span>
                    <span className="text-gray-400">pricing</span>
                  </div>
                ) : (
                  <div className="flex items-baseline gap-2">
                    <span className="text-5xl font-bold text-white">
                      {plan.id === 'free' ? 
                        '₹0' : 
                        formatPrice(
                          billingCycle === 'monthly' ? plan.monthly.price : plan.yearly.price, 
                          plan.currency
                        )
                      }
                    </span>
                    {plan.id !== 'free' && (
                      <span className="text-gray-400 text-lg">
                        /{billingCycle === 'monthly' ? 'month' : 'year'}
                      </span>
                    )}
                  </div>
                )}
              </div>

              <ul className="feature-list">
                {plan.features.map((feature: string, i: number) => (
                  <li key={i} className="feature-item">
                    <Check className="w-5 h-5 feature-icon" />
                    <span className="text-gray-300 text-sm leading-relaxed">
                      {feature}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="mt-8">
                {plan.id === 'free' && (
                  <button 
                    onClick={onSelectFreePlan} 
                    className="btn btn-secondary"
                  >
                    Get Started Free
                  </button>
                )}
                {plan.id === 'developer' && (
                  <button 
                    onClick={() => onSelectPaidPlan(plan.id, billingCycle)} 
                    className="btn btn-primary"
                  >
                    Choose Developer
                  </button>
                )}
                {plan.id === 'professional' && (
                  <button 
                    onClick={() => onSelectPaidPlan(plan.id, billingCycle)} 
                    className="btn btn-secondary"
                  >
                    Choose Professional
                  </button>
                )}
                {plan.id === 'enterprise' && (
                  <button 
                    onClick={() => window.open('mailto:sales@example.com', '_blank')} 
                    className="btn btn-secondary"
                  >
                    Contact Sales
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}