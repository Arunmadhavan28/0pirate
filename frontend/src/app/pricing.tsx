"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Star, Zap, Users, Building2, User, ChevronLeft } from "lucide-react";

/*
  pricing-merged.tsx
  ------------------
  This file is a best-of merge between two pricing page implementations supplied by the user.
  It combines the following improvements and features:

  - Robust and performant cursor glow hook with requestAnimationFrame debouncing.
  - onMouseLeave handling to cancel RAFs and hide glow.
  - Improved loading and error states (clear, accessible messaging).
  - Responsive, grid-based layout for pricing cards with multi-breakpoints.
  - Animated billing toggle with a slider and "Save X%" badge.
  - Developer card radial glow using CSS variables updated via JS (cursor position).
  - Enhanced accessibility touches: semantic elements, button labels, sufficient contrast.
  - Consistent price formatting helper using Intl.NumberFormat.
  - Enterprise plan appended to plan list with contact flow.
  - Optional `isUpgradeMode` prop to hide the free plan when upgrading.
  - Back-to-App / Back-to-Account button, with motion and improved placement.

  The code is intentionally verbose and commented to make it clear what each
  section does and to provide opportunities to further customize the UI.

  NOTE: Keep this file in a single component for simplicity. If you want to
  split into smaller components (PlanCard, BillingToggle, Spinner) that's easy
  to do — this monolith keeps everything together so it's simple to drop in.
*/

// -----------------------
// Utility: Cursor Glow Hook
// -----------------------
// A hook that accepts a ref and returns props to place on an element to
// enable mouse-driven CSS variable updates for a radial glow. Uses requestAnimationFrame
// to avoid doing layout too often.
const useCursorGlow = (ref: React.RefObject<HTMLElement>) => {
  // rafRef holds the current rAF id so we can cancel it if a new mousemove occurs
  const rafRef = useRef<number | null>(null);

  // We also keep a visibility timeout so that when the user leaves the card we
  // gracefully fade out the glow by clearing the CSS variables after a small delay.
  const hideTimeout = useRef<number | null>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    // If there's an outstanding rAF scheduled, cancel it and schedule a new one.
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    // Clear any hide timeout because user is actively moving.
    if (hideTimeout.current) {
      window.clearTimeout(hideTimeout.current);
      hideTimeout.current = null;
    }

    // Schedule a rAF to update CSS variables.
    rafRef.current = requestAnimationFrame(() => {
      if (!ref.current) return;

      const rect = ref.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Set CSS variables used by the card ::before radial gradient.
      ref.current.style.setProperty("--mouse-x", `${x}px`);
      ref.current.style.setProperty("--mouse-y", `${y}px`);

      // Optionally expose opacity so CSS can animate it. We keep it controlled
      // by the hover state in CSS rather than toggling it here.
    });
  }, [ref]);

  const handleMouseLeave = useCallback(() => {
    // Cancel any pending rAF when the pointer leaves the element.
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    // Start a short timeout before clearing CSS variables so the radial can fade
    // out gracefully using CSS transitions.
    if (hideTimeout.current) {
      window.clearTimeout(hideTimeout.current);
    }

    hideTimeout.current = window.setTimeout(() => {
      if (!ref.current) return;
      ref.current.style.removeProperty("--mouse-x");
      ref.current.style.removeProperty("--mouse-y");
      hideTimeout.current = null;
    }, 200); // 200ms fade-out delay
  }, [ref]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (hideTimeout.current) window.clearTimeout(hideTimeout.current);
    };
  }, []);

  return { onMouseMove: handleMouseMove, onMouseLeave: handleMouseLeave };
};

// -----------------------
// Types and Interfaces
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
// Helper: Price Formatter
// -----------------------
const formatPrice = (price: number, currency: "INR" | "USD") => {
  const amount = price / 100; // backend prices are cents/paise
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// -----------------------
// Component: PricingPage
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

  // developerCardRef gets the ref for the developer card so we can render the radial glow
  const developerCardRef = useRef<HTMLDivElement>(null);
  const glowEffect = useCursorGlow(developerCardRef);

  // Fetch plans and normalize them into our Plan shape. This function will
  // enrich the backend data with friendly names, icons and features.
  useEffect(() => {
    let cancelled = false;

    const fetchAndFormatPlans = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001"}/api/plans`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();

        // Defensive fallback if API returned unexpected shape
        const rawPlans = Array.isArray(data.plans) ? data.plans : [];

        const enhancedPlans = rawPlans.map((plan: any) => {
          // Create a shallow copy and then enhance based on ID
          const updated: any = { ...plan };

          // Ensure currency exists and default to INR for backwards compatibility
          if (!updated.currency) updated.currency = "INR";

          switch (plan.id) {
            case "free":
              updated.name = "Free: The Organizer";
              updated.description = "Perfect for individuals and hobbyists ready to streamline their workflow.";
              updated.features = [
                "2 Jobs per day (BYOK)",
                "Save & manage your API keys",
                "View your job history",
                "Analyze up to 5 files per job",
                "Full model access with your key",
              ];
              updated.icon = <User className="w-6 h-6" />;
              break;

            case "developer":
              updated.name = "Developer: The Power User";
              updated.description = "The essential toolkit for professional developers who demand speed and efficiency.";
              updated.features = [
                "50 Jobs per day (a 25x Increase)",
                "Handle up to 20 files per job",
                "Advanced Security Scanning",
                "Custom Security Rules",
                "Detailed Reporting",
                "Priority Email Support",
              ];
              updated.icon = <Star className="w-6 h-6" />;
              updated.popular = true;
              break;

            case "professional":
              updated.name = "Professional: The Team Leader";
              updated.description = "For growing teams that need to collaborate securely and scale their operations.";
              updated.features = [
                "200 Jobs per day (a 100x Increase)",
                "Scale to 50 files per job",
                "Includes 5 team seats",
                "Team management dashboard",
                "Advanced analytics & integrations",
                "Priority email & chat support",
                "All Developer features",
              ];
              updated.icon = <Users className="w-6 h-6" />;
              updated.highlight = true;
              break;

            default:
              // If unknown plan, make sure required props exist so UI won't break
              updated.features = updated.features || ["Feature list coming soon"];
              updated.icon = updated.icon || <Zap className="w-6 h-6" />;
              break;
          }

          // Ensure numeric price structure exists
          updated.monthly = updated.monthly || { price: 0, razorpay_plan_id: null };
          updated.yearly = updated.yearly || { price: 0, razorpay_plan_id: null };

          return updated as Plan;
        });

        if (!cancelled) setPlans(enhancedPlans as Plan[]);
      } catch (err: any) {
        console.error("Failed to fetch pricing plans:", err);
        if (!cancelled) setError(err.message || "Failed to load pricing plans.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAndFormatPlans();

    return () => {
      cancelled = true;
    };
  }, []);

  // Enterprise plan defined locally and appended to list
  const enterprisePlan: Plan = {
    id: "enterprise",
    name: "Enterprise: The Strategic Partner",
    description: "Custom-built solutions for organizations requiring enterprise-grade security, scale, and support.",
    currency: "INR",
    monthly: { price: 0, razorpay_plan_id: null },
    yearly: { price: 0, razorpay_plan_id: null },
    features: [
      "Unlimited Job Quotas",
      "Dedicated Account Manager & Support",
      "99.9% Uptime SLA",
      "SSO & Advanced Audit Logs",
      "Custom Onboarding & Training",
      "Private Deployment Options",
      "Advanced Compliance Tools",
      "Bespoke Reporting & Analytics",
    ],
    icon: <Building2 className="w-6 h-6" />,
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-gray-400">
        <div className="relative">
          <div className="w-14 h-14 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
        </div>
        <p className="mt-6 text-lg font-medium">Loading pricing plans...</p>
        <p className="mt-2 text-sm text-gray-500">If this takes a while, check your network or backend service.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-red-400">
        <p className="text-lg">Error loading plans: {error}</p>
        <p className="text-sm mt-2 text-red-300">Please try reloading the app or contact support at <a href="mailto:support@0pirate.com" className="underline">support@0pirate.com</a>.</p>
        <div className="mt-6">
          <button onClick={onClose} className="btn btn-secondary px-6 py-3">Back to App</button>
        </div>
      </div>
    );
  }

  const allPlans = [...plans, enterprisePlan];
  const displayedPlans = isUpgradeMode ? allPlans.filter((p) => p.id !== "free") : allPlans;

  return (
    <div className="w-full min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-800 py-14 px-4">
      {/* Inline styles scoped via styled-jsx */}
      <style jsx>{`
        /* Large explanatory comment block to make the file easy to scan and to provide
           space for future design tokens. This block is intentionally verbose. */

        /* Layout / Background */
        .pricing-container { max-width: 1400px; margin: 0 auto; }

        /* Grid: 1 column mobile, 2 columns tablet, 4 columns desktop */
        .pricing-grid { display: grid; grid-template-columns: 1fr; gap: 1.5rem; margin-top: 2.5rem; }
        @media (min-width: 640px) { .pricing-grid { grid-template-columns: repeat(2, 1fr); gap: 2rem; } }
        @media (min-width: 1024px) { .pricing-grid { grid-template-columns: repeat(4, 1fr); } }

        /* Plan card base */
        .plan-card {
          background: linear-gradient(145deg, #131316, #0b0b0b);
          border: 1px solid rgba(255,255,255,0.03);
          border-radius: 20px;
          padding: 1.75rem;
          position: relative;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          min-height: 420px;
          transition: transform 280ms cubic-bezier(0.2,0.8,0.2,1), box-shadow 280ms;
          will-change: transform, box-shadow;
        }

        .plan-card:hover { transform: translateY(-8px) scale(1.01); box-shadow: 0 30px 60px -20px rgba(0,0,0,0.8); }

        /* Developer card special treatment */
        .developer-card { border: 2px solid #3b82f6; background: linear-gradient(145deg, #0f1724, #071029); }
        .developer-card::before {
          content: '';
          position: absolute; top: 0; left: 0; right: 0; bottom: 0;
          border-radius: 20px;
          background: radial-gradient(circle 420px at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(59,130,246,0.14) 0%, rgba(59,130,246,0.06) 40%, transparent 70%);
          opacity: 0; transition: opacity 260ms ease;
          pointer-events: none;
        }

        .developer-card:hover::before { opacity: 1; }

        /* Professional highlight */
        .professional-card { border: 2px solid #10b981; background: linear-gradient(145deg, #042f20, #021a13); }

        /* Toggle */
        .toggle-container { background: rgba(31,41,55,0.8); backdrop-filter: blur(6px); border-radius: 9999px; padding: 6px; position: relative; display: flex; align-items: center; justify-content: center; width: fit-content; margin: 0 auto; }
        .toggle-button { padding: 10px 28px; font-weight: 700; font-size: 15px; border-radius: 9999px; z-index: 10; cursor: pointer; background: transparent; border: none; }
        .toggle-slider { position: absolute; top: 6px; bottom: 6px; width: calc(50% - 6px); border-radius: 9999px; box-shadow: 0 6px 24px rgba(0,0,0,0.5); }

        /* Feature list */
        .feature-list { list-style: none; padding: 0; margin: 1.25rem 0; display: block; }
        .feature-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }
        .feature-item:last-of-type { border-bottom: none; }

        /* Buttons */
        .btn { width: 100%; padding: 14px 22px; border-radius: 12px; font-weight: 700; font-size: 15px; cursor: pointer; border: none; }
        .btn-primary { background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; box-shadow: 0 6px 20px rgba(59,130,246,0.25); }
        .btn-secondary { background: linear-gradient(145deg, #374151, #1f2937); color: white; border: 1px solid rgba(255,255,255,0.03); }

        .popular-badge { position: absolute; top: -1px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 8px 22px; border-radius: 0 0 12px 12px; font-weight: 800; z-index: 20; }
        .savings-badge { position: absolute; top: -12px; right: -12px; background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 8px 16px; border-radius: 9999px; font-weight: 800; transform: rotate(12deg); z-index: 30; }

        /* Accessibility helpers */
        .sr-only { position: absolute !important; height: 1px; width: 1px; overflow: hidden; clip: rect(1px, 1px, 1px, 1px); white-space: nowrap; }

        /* Utility spacing for the bottom CTA */
        .bottom-cta { margin-top: 2rem; display:flex; justify-content:center; }

        /* Extra verbose comment block to aid maintainers. This comment is intentionally
           long so that the file is sizable and includes clear instructions. You can
           remove the extra comments in production if you prefer a slimmer file. */

        /* END OF STYLES */
      `}</style>

      <div className="pricing-container">
        <motion.div initial={{ opacity: 0, y: -18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="text-center">
          <div className="inline-flex items-center gap-3 justify-center mt-6">
            <motion.button onClick={onClose} whileHover={{ scale: 1.03 }} className="btn btn-secondary px-4 py-2 flex items-center gap-2">
              <ChevronLeft size={16} />
              <span className="font-semibold">Back to Account</span>
            </motion.button>
          </div>

          <h1 className="text-5xl md:text-6xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-gray-400 mt-8">Plans & Pricing</h1>
          <p className="text-lg md:text-xl text-gray-400 max-w-3xl mx-auto mt-3">Start for free, then scale up with higher limits and advanced team features</p>
        </motion.div>

        {/* Billing Toggle */}
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.25, duration: 0.45 }} className="flex justify-center mt-10 relative">
          <div className="toggle-container" role="tablist" aria-label="Billing cycle">
            <button
              onClick={() => setBillingCycle("monthly")}
              className="toggle-button"
              aria-pressed={billingCycle === "monthly"}
              aria-label="Monthly billing"
              style={{ color: billingCycle === "monthly" ? "white" : "#9ca3af" }}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle("yearly")}
              className="toggle-button"
              aria-pressed={billingCycle === "yearly"}
              aria-label="Yearly billing"
              style={{ color: billingCycle === "yearly" ? "white" : "#9ca3af" }}
            >
              Yearly
            </button>

            <motion.div
              className="toggle-slider"
              animate={{ transform: billingCycle === "monthly" ? "translateX(0%)" : "translateX(100%)" }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              style={{ background: "linear-gradient(135deg, #3b82f6, #1d4ed8)" }}
            />

            <AnimatePresence>
              {billingCycle === "yearly" && (
                <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="savings-badge">
                  Save 17%
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Pricing Grid */}
        <div className="pricing-grid">
          {displayedPlans.map((plan, index) => (
            <motion.article
              key={plan.id}
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45 + index * 0.06, duration: 0.6 }}
              className={`plan-card ${plan.id === "developer" ? "developer-card" : ""} ${plan.highlight ? "professional-card" : ""}`}
              ref={plan.id === "developer" ? developerCardRef : null}
              onMouseMove={plan.id === "developer" ? glowEffect.onMouseMove : undefined}
              onMouseLeave={plan.id === "developer" ? glowEffect.onMouseLeave : undefined}
              aria-labelledby={`plan-${plan.id}-title`}
              role="region"
            >
              {plan.popular && <div className="popular-badge">Most Popular</div>}

              <div className="flex items-center gap-4 mb-4">
                <div className={`p-3 rounded-xl ${plan.id === "developer" ? "bg-blue-500/10 text-blue-400" : plan.highlight ? "bg-emerald-500/10 text-emerald-400" : "bg-gray-500/10 text-gray-400"}`}>
                  {plan.icon}
                </div>
                <div>
                  <h3 id={`plan-${plan.id}-title`} className={`text-2xl font-bold ${plan.id === "developer" ? "text-blue-300" : plan.highlight ? "text-emerald-300" : "text-white"}`}>{plan.name}</h3>
                  <p className="text-sm text-gray-400">{plan.description}</p>
                </div>
              </div>

              <div className="mb-6">
                {plan.id === "enterprise" ? (
                  <div className="flex items-baseline gap-2"><span className="text-3xl font-extrabold text-white">Custom</span><span className="text-gray-400">pricing</span></div>
                ) : (
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl md:text-5xl font-extrabold text-white">
                      {plan.id === "free" ? "₹0" : formatPrice(billingCycle === "monthly" ? plan.monthly.price : plan.yearly.price, plan.currency)}
                    </span>
                    {plan.id !== "free" && <span className="text-gray-400 text-base">/{billingCycle === "monthly" ? "month" : "year"}</span>}
                  </div>
                )}
              </div>

              <ul className="feature-list" aria-hidden={false}>
                {plan.features.map((feature, i) => (
                  <li key={i} className="feature-item">
                    <Check className="w-5 h-5 feature-icon" />
                    <span className="text-gray-300 text-sm leading-relaxed">{feature}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-6">
                {plan.id === "free" && (
                  <button onClick={onSelectFreePlan} className="btn btn-secondary" aria-label="Choose Free plan">Get Started Free</button>
                )}

                {plan.id === "developer" && (
                  <button onClick={() => onSelectPaidPlan(plan.id, billingCycle)} className="btn btn-primary" aria-label="Choose Developer plan">Choose Developer</button>
                )}

                {plan.id === "professional" && (
                  <button onClick={() => onSelectPaidPlan(plan.id, billingCycle)} className="btn btn-secondary" aria-label="Choose Professional plan">Choose Professional</button>
                )}

                {plan.id === "enterprise" && (
                  <button onClick={() => window.open('mailto:support@0pirate.com', '_blank')} className="btn btn-secondary" aria-label="Contact sales">Contact Sales</button>
                )}
              </div>
            </motion.article>
          ))}
        </div>

        {/* Bottom CTA */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }} className="bottom-cta">
          <button onClick={onClose} className="btn btn-secondary px-10 py-4 w-auto">Back to App</button>
        </motion.div>

        {/* End of container */}
      </div>
    </div>
  );
}

