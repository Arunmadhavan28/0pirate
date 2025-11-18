"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Star, Zap, Users, Building2, User, ChevronLeft } from "lucide-react";

// -----------------------
// Utility: Cursor Glow Hook
// -----------------------
const useCursorGlow = (ref: React.RefObject<HTMLElement>) => {
  const rafRef = useRef<number | null>(null);
  const hideTimeout = useRef<number | null>(null);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (hideTimeout.current) {
        window.clearTimeout(hideTimeout.current);
        hideTimeout.current = null;
      }
      rafRef.current = requestAnimationFrame(() => {
        if (!ref.current) return;
        const rect = ref.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        ref.current.style.setProperty("--mouse-x", `${x}px`);
        ref.current.style.setProperty("--mouse-y", `${y}px`);
      });
    },
    [ref]
  );

  const handleMouseLeave = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (hideTimeout.current) window.clearTimeout(hideTimeout.current);

    hideTimeout.current = window.setTimeout(() => {
      if (!ref.current) return;
      ref.current.style.removeProperty("--mouse-x");
      ref.current.style.removeProperty("--mouse-y");
      hideTimeout.current = null;
    }, 200);
  }, [ref]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (hideTimeout.current) window.clearTimeout(hideTimeout.current);
    };
  }, []);

  return { onMouseMove: handleMouseMove, onMouseLeave: handleMouseLeave };
};

// -----------------------
// Types
// -----------------------
interface Plan {
  id: string;
  name: string;
  description: string;
  currency: "INR" | "USD";
  monthly: { price: number; razorpay_plan_id: string | null };
  yearly: { price: number; razorpay_plan_id: string | null };
  features: string[];
  icon?: React.ReactNode;
  popular?: boolean;
  highlight?: boolean;
}

interface PricingPageProps {
  onClose: () => void;
  onSelectFreePlan: () => void;
  onSelectPaidPlan: (planId: string, billingCycle: "monthly" | "yearly") => void;
  isUpgradeMode?: boolean;
}

// -----------------------
// Helper
// -----------------------
const formatPrice = (price: number, currency: "INR" | "USD") => {
  const amount = price / 100;
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// -----------------------
// Component
// -----------------------
export default function PricingPage({
  onClose,
  onSelectFreePlan,
  onSelectPaidPlan,
  isUpgradeMode,
}: PricingPageProps) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("yearly");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const developerCardRef = useRef<HTMLDivElement>(null);
  const glowEffect = useCursorGlow(developerCardRef);

  useEffect(() => {
    let cancelled = false;
    const fetchPlans = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001"}/api/plans`);
        if (!response.ok) throw new Error(`HTTP error ${response.status}`);
        const data = await response.json();
        const rawPlans = Array.isArray(data.plans) ? data.plans : [];

        const enhancedPlans = rawPlans.map((plan: any) => {
          const updated: any = { ...plan };
          if (!updated.currency) updated.currency = "INR";
          switch (plan.id) {
            case "free":
              updated.name = "Free: The Organizer";
              updated.description = "Perfect for individuals and hobbyists.";
              updated.features = ["2 Jobs/day", "Save & manage API keys", "View job history", "5 files per job"];
              updated.icon = <User className="w-6 h-6" />;
              break;
            case "developer":
              updated.name = "Developer: The Power User";
              updated.description = "For professional developers needing speed and efficiency.";
              updated.features = ["50 Jobs/day", "20 files/job", "Advanced Security", "Custom Rules", "Reporting", "Priority Email Support"];
              updated.icon = <Star className="w-6 h-6" />;
              updated.popular = true;
              break;
            case "professional":
              updated.name = "Professional: The Team Leader";
              updated.description = "For teams that need secure collaboration.";
              updated.features = ["200 Jobs/day", "50 files/job", "5 Team seats", "Dashboard", "Advanced analytics", "Priority chat support"];
              updated.icon = <Users className="w-6 h-6" />;
              updated.highlight = true;
              break;
            default:
              updated.features = updated.features || ["Feature list coming soon"];
              updated.icon = updated.icon || <Zap className="w-6 h-6" />;
              break;
          }
          return updated as Plan;
        });

        if (!cancelled) setPlans(enhancedPlans);
      } catch (err: any) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchPlans();
    return () => {
      cancelled = true;
    };
  }, []);

  const enterprisePlan: Plan = {
    id: "enterprise",
    name: "Enterprise: The Strategic Partner",
    description: "Custom-built solutions for large organizations.",
    currency: "INR",
    monthly: { price: 0, razorpay_plan_id: null },
    yearly: { price: 0, razorpay_plan_id: null },
    features: ["Unlimited Jobs", "Dedicated Manager", "99.9% SLA", "SSO", "Custom Onboarding", "Private Deployments"],
    icon: <Building2 className="w-6 h-6" />,
  };

  if (loading) return <p className="text-center text-gray-400">Loading plans...</p>;
  if (error) return <p className="text-center text-red-400">Error: {error}</p>;

  const allPlans = [...plans, enterprisePlan];
  const displayedPlans = isUpgradeMode ? allPlans.filter((p) => p.id !== "free") : allPlans;

  return (
    <div className="w-full min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-800 py-14 px-4">
      <style jsx>{`
        .pricing-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
          margin-top: 2.5rem;
        }
        @media (min-width: 768px) {
          .pricing-grid {
            grid-template-columns: repeat(3, 1fr);
          }
        }
        .plan-card {
          background: #0b0b0b;
          border-radius: 20px;
          padding: 1.75rem;
          position: relative;
          display: flex;
          flex-direction: column;
          transition: 0.3s;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .plan-card:hover {
          transform: translateY(-6px);
        }
        .developer-card {
          border: 2px solid #3b82f6;
        }
        .professional-card {
          border: 2px solid #10b981;
        }
        .popular-badge {
          position: absolute;
          top: 12px;
          left: 12px;
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          color: white;
          padding: 4px 12px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: bold;
        }
        .toggle-container {
          display: flex;
          align-items: center;
          background: rgba(31, 41, 55, 0.9);
          border-radius: 9999px;
          padding: 4px;
          position: relative;
        }
        .toggle-option {
          flex: 1;
          text-align: center;
          padding: 8px 18px;
          cursor: pointer;
          font-weight: 600;
          font-size: 14px;
          color: #9ca3af;
        }
        .toggle-option.active {
          color: white;
        }
        .toggle-slider {
          position: absolute;
          top: 4px;
          bottom: 4px;
          width: 50%;
          border-radius: 9999px;
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          transition: transform 0.3s ease;
        }
      `}</style>

      <div className="pricing-container max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
  onClick={onClose}
  className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700/50 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-500/50"
>
  <ChevronLeft size={16} />
  <span>Back to Account</span>
</button>
        </div>
        <h1 className="text-5xl font-extrabold text-center mt-6 bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-gray-400">
          Plans & Pricing
        </h1>
        <p className="text-center text-gray-400 mt-2">
          Start free, then scale up with higher limits and team features
        </p>

        {/* Toggle */}
        <div className="flex justify-center mt-10">
          <div className="toggle-container w-64">
            <motion.div
              className="toggle-slider"
              animate={{ transform: billingCycle === "monthly" ? "translateX(0%)" : "translateX(100%)" }}
            />
            <div
              className={`toggle-option ${billingCycle === "monthly" ? "active" : ""}`}
              onClick={() => setBillingCycle("monthly")}
            >
              Monthly
            </div>
            <div
              className={`toggle-option ${billingCycle === "yearly" ? "active" : ""}`}
              onClick={() => setBillingCycle("yearly")}
            >
              Yearly <span className="text-emerald-400 text-xs font-bold ml-1">Save 17%</span>
            </div>
          </div>
        </div>

        {/* Grid */}
        <div className="pricing-grid mt-10">
          {displayedPlans.map((plan, index) => (
            <div
              key={plan.id}
              ref={plan.id === "developer" ? developerCardRef : null}
              {...(plan.id === "developer" ? glowEffect : {})}
              className={`plan-card ${plan.id === "developer" ? "developer-card" : ""} ${
                plan.highlight ? "professional-card" : ""
              }`}
            >
              {plan.popular && <div className="popular-badge">Most Popular</div>}
              <div className="flex items-center gap-3 mb-3">
                {plan.icon}
                <h3 className="text-xl font-bold text-white">{plan.name}</h3>
              </div>
              <p className="text-gray-400 mb-4">{plan.description}</p>
              <div className="text-3xl font-extrabold text-white mb-4">
                {plan.id === "enterprise"
                  ? "Custom Pricing"
                  : plan.id === "free"
                  ? "₹0"
                  : formatPrice(billingCycle === "monthly" ? plan.monthly.price : plan.yearly.price, plan.currency)}
              </div>
              <ul className="list-none text-sm text-gray-300 space-y-2 mb-6">
  {plan.features.map((f, i) => (
    <li key={i} className="flex gap-2 items-start">
      <Check className="w-4 h-4 mt-0.5 flex-shrink-0 text-emerald-400" />
      <span>{f}</span>
    </li>
  ))}
</ul>
              <div className="mt-auto">
                {plan.id === "free" && (
                  <button onClick={onSelectFreePlan} className="btn btn-secondary w-full">
                    Get Started Free
                  </button>
                )}
                {plan.id === "developer" && (
                  <button onClick={() => onSelectPaidPlan(plan.id, billingCycle)} className="btn btn-primary w-full">
                    Choose Developer
                  </button>
                )}
                {plan.id === "professional" && (
                  <button onClick={() => onSelectPaidPlan(plan.id, billingCycle)} className="btn btn-secondary w-full">
                    Choose Professional
                  </button>
                )}
                {plan.id === "enterprise" && (
                  <button
                    onClick={() => window.location.href = "mailto:support@0pirate.com"}
                    className="btn btn-secondary w-full"
                  >
                    Contact Sales
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
