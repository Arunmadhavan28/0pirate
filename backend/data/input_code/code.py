"use client";

import React, { useState, useEffect, useMemo, useRef } from 'react';

// --- Mocks & Types ---
// Simulates API calls with deliberate inconsistencies and delays.

type Transaction = {
  id: string;
  amount: number | string; // BUG: amount can be a string, leading to NaN issues.
  type: 'income' | 'expense';
  date: string;
  description?: string;
};

type UserProfile = {
  id: string;
  name: string;
  preferences: {
    theme: 'dark' | 'light';
    // Deliberately make avatar optional to test null-checking.
    avatarUrl?: string;
  }
};

const mockApi = {
  fetchUserProfile: (userId: string): Promise<UserProfile> =>
    new Promise(resolve =>
      setTimeout(() => {
        console.log("API: Fetched User Profile");
        resolve({
          id: userId,
          name: 'Alex Doe',
          preferences: { theme: 'dark' },
        });
      }, 800)
    ),
  fetchTransactions: (): Promise<Transaction[]> =>
    new Promise(resolve =>
      setTimeout(() => {
        console.log("API: Fetched Transactions");
        resolve([
          { id: 't1', amount: 3000, type: 'income', date: '2025-09-10' },
          { id: 't2', amount: '250.75', type: 'expense', date: '2025-09-11' }, // Note: string amount
          { id: 't3', amount: 50, type: 'expense', date: '2025-09-12' },
          { id: 't4', amount: 5000, type: 'income', date: '2025-09-15' },
          { id: 't5', amount: 1200, type: 'expense', date: '2025-09-18' },
        ]);
      }, 1200)
    ),
};


// --- The Component ---

export default function Dashboard() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [filter, setFilter] = useState<'all' | 'income' | 'expense'>('all');
  const [summary, setSummary] = useState({ income: 0, expense: 0, net: 0 });
  const [lastNote, setLastNote] = useState('');
  const [refreshCount, setRefreshCount] = useState(0);

  const latestNoteRef = useRef<HTMLParagraphElement>(null);

  // BUG 1: Race Condition & Improper Dependency Handling
  // This effect tries to access `user.preferences` which might still be null
  // when transactions are set first, causing a crash.
  useEffect(() => {
    console.log("Theme effect triggered. Current theme:", user?.preferences.theme);
    // This logic is trivial, but it demonstrates the dependency bug.
    if (user?.preferences.theme === 'dark') {
      document.body.style.backgroundColor = '#1a1a1a';
    }
  }, [transactions]); // BUG: Should depend on `user`, not `transactions`.

  // BUG 2: Initial Data Fetch with potential race condition.
  useEffect(() => {
    const loadData = async () => {
      // Using Promise.all is good, but the effects above are not robust to the race condition.
      const [userData, transactionData] = await Promise.all([
        mockApi.fetchUserProfile("user-123"),
        mockApi.fetchTransactions()
      ]);
      setUser(userData);
      setTransactions(transactionData);
    };
    loadData();
  }, []); // Runs only once, which is intended.

  // BUG 3: Stale Closure in setInterval & Memory Leak
  // The auto-refresh will always log `refreshCount` as 0 and never clears the interval.
  useEffect(() => {
    const autoRefresh = setInterval(() => {
      console.log(`Auto-refreshing... Refresh count is ${refreshCount}`); // BUG: refreshCount is stale
      setRefreshCount(refreshCount + 1); // BUG: This uses the stale value
    }, 10000);

    // BUG: Missing cleanup function `return () => clearInterval(autoRefresh);`
  }, []);

  // BUG 4: Expensive calculation not memoized correctly.
  // The dependencies are missing, so the summary is calculated only once.
  const calculateSummary = () => {
    console.log("Calculating summary...");
    const newSummary = transactions.reduce((acc, t) => {
        const amount = parseFloat(t.amount as string); // Attempts to fix string amount, but is risky
        if (t.type === 'income') acc.income += amount;
        else acc.expense += amount;
        return acc;
      },
      { income: 0, expense: 0 }
    );
    // BUG: The `net` calculation is incorrect.
    setSummary({ ...newSummary, net: newSummary.income + newSummary.expense });
  };
  useEffect(() => {
    calculateSummary();
  }, []); // BUG: Missing `transactions` in dependency array.

  // BUG 5: Inefficient rendering. This function is recreated on every render.
  const getFilteredTransactions = () => {
    if (filter === 'all') return transactions;
    return transactions.filter(t => t.type === filter);
  };

  // BUG 6: Direct DOM Manipulation & Cross-Site Scripting (XSS) Vulnerability
  const handleNoteChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const note = e.target.value;
    if (latestNoteRef.current) {
      // BUG: Using innerHTML directly with user input is a major XSS risk.
      // Try typing: <img src=x onerror=alert('XSS-ATTACK')>
      latestNoteRef.current.innerHTML = `Latest Note: ${note}`;
    }
  };
  
  // BUG 7: Null-checking error. App will crash because `user.preferences.avatarUrl`
  // is accessed without checking if `avatarUrl` exists.
  const userAvatar = user?.preferences.avatarUrl;

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', color: '#fff' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between' }}>
        {/* BUG 8: Will crash if `user` is null initially. */}
        <h1>Welcome, {user!.name}!</h1>
        {/* The line below will crash the app */}
        <img src={userAvatar} alt="User Avatar" style={{ width: '50px', height: '50px', borderRadius: '50%' }}/>
      </header>

      <section style={{ margin: '2rem 0' }}>
        <h2>Financial Summary</h2>
        {/* Because of Bug #4, these values will be incorrect and won't update. */}
        <p>Total Income: ${summary.income.toFixed(2)}</p>
        <p>Total Expenses: ${summary.expense.toFixed(2)}</p>
        {/* Because of Bug #4, this calculation is logically wrong. */}
        <p>Net Balance: ${summary.net.toFixed(2)}</p>
      </section>

      <section>
        <h2>Transactions</h2>
        <div>
          <button onClick={() => setFilter('all')}>All</button>
          <button onClick={() => setFilter('income')}>Income</button>
          <button onClick={() => setFilter('expense')}>Expense</button>
        </div>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {/* Because of Bug #5, this list re-renders inefficiently. */}
          {getFilteredTransactions().map(t => (
            <li key={t.id} style={{ background: '#333', margin: '0.5rem 0', padding: '1rem', borderRadius: '5px' }}>
              <span>{t.date}</span>
              <strong style={{ margin: '0 1rem' }}>{t.type === 'income' ? '+' : '-'}${t.amount}</strong>
              <span>{t.description || 'No description'}</span>
            </li>
          ))}
        </ul>
      </section>

      <footer style={{ marginTop: '2rem' }}>
        <h2>Notes</h2>
        <input
          type="text"
          placeholder="Add a new note..."
          onChange={handleNoteChange} // BUG 6 is triggered here
          style={{ width: '100%', padding: '0.5rem' }}
        />
        <p ref={latestNoteRef}>Latest Note: (none)</p>
      </footer>
    </div>
  );
}