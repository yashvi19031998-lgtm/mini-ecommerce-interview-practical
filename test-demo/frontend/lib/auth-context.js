'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from './supabase';

const AuthContext = createContext({});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. Check existing local demo session first
    if (typeof window !== 'undefined') {
      const savedLocalUser = localStorage.getItem('lead_hub_demo_user');
      if (savedLocalUser) {
        try {
          const parsed = JSON.parse(savedLocalUser);
          if (parsed && parsed.email) {
            setUser(parsed);
            setLoading(false);
            return;
          }
        } catch (e) {
          localStorage.removeItem('lead_hub_demo_user');
        }
      }
    }

    // 2. Check Supabase session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });

    // 3. Listen for Supabase auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session?.user) {
        setUser(session.user);
      }
      setLoading(false);
    });

    return () => {
      subscription?.unsubscribe();
    };
  }, []);

  // Sign In
  const signIn = async (email, password) => {
    const cleanEmail = email.trim();
    const { data, error } = await supabase.auth.signInWithPassword({
      email: cleanEmail,
      password,
    });
    if (error) throw error;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('lead_hub_demo_user');
    }
    return data;
  };

  // Sign Up (Register)
  const signUp = async (email, password, fullName = '') => {
    const cleanEmail = email.trim();
    const { data, error } = await supabase.auth.signUp({
      email: cleanEmail,
      password,
      options: {
        data: {
          full_name: fullName,
        },
      },
    });
    if (error) throw error;
    return data;
  };

  // Sign Out
  const signOut = async () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('lead_hub_demo_user');
    }
    try {
      await supabase.auth.signOut();
    } catch (e) {
      // Ignore if offline
    }
    setUser(null);
    setSession(null);
  };

  // Quick Demo / Local Login (persists in localStorage)
  const bypassDemoLogin = (customUser = null) => {
    const userToSet = customUser || {
      id: 'demo-admin-id',
      email: 'admin@sangeetainfotech.com',
      user_metadata: { full_name: 'Lead Admin' }
    };
    if (typeof window !== 'undefined') {
      localStorage.setItem('lead_hub_demo_user', JSON.stringify(userToSet));
    }
    setUser(userToSet);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        signIn,
        signUp,
        signOut,
        bypassDemoLogin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
