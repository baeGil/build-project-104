"use client";

import { useState, useEffect, Dispatch, SetStateAction } from "react";

/**
 * A custom hook that persists state to localStorage.
 * Handles SSR by checking for window availability.
 * Includes error handling for JSON parse/stringify operations.
 */
export function usePersistedState<T>(
  key: string,
  defaultValue: T
): [T, Dispatch<SetStateAction<T>>] {
  // Initialize with default value for SSR
  const [state, setState] = useState<T>(defaultValue);
  const [isHydrated, setIsHydrated] = useState(false);

  // Load from localStorage on mount (client-side only)
  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      const stored = localStorage.getItem(key);
      if (stored !== null) {
        const parsed = JSON.parse(stored);
        setState(parsed);
      }
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      // Keep default value on error
    }
    setIsHydrated(true);
  }, [key]);

  // Persist to localStorage whenever state changes
  useEffect(() => {
    if (typeof window === "undefined" || !isHydrated) return;

    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch (error) {
      console.error(`Error writing localStorage key "${key}":`, error);
    }
  }, [key, state, isHydrated]);

  return [state, setState];
}
