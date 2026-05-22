import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const STORAGE_KEY = "gmail-genie-developer-mode";

const DeveloperModeContext = createContext(null);

function readDeveloperMode() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function DeveloperModeProvider({ children }) {
  const [developerMode, setDeveloperMode] = useState(readDeveloperMode);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, developerMode ? "true" : "false");
    } catch {
      /* ignore */
    }
  }, [developerMode]);

  const toggleDeveloperMode = useCallback(() => {
    setDeveloperMode((v) => !v);
  }, []);

  const value = useMemo(
    () => ({ developerMode, setDeveloperMode, toggleDeveloperMode }),
    [developerMode, toggleDeveloperMode],
  );

  return createElement(DeveloperModeContext.Provider, { value }, children);
}

export function useDeveloperMode() {
  const ctx = useContext(DeveloperModeContext);
  if (!ctx) {
    throw new Error("useDeveloperMode must be used within DeveloperModeProvider");
  }
  return ctx;
}

export function hasCompletedFirstApply() {
  try {
    return localStorage.getItem("gmail-genie-has-applied") === "true";
  } catch {
    return false;
  }
}

export function markFirstApplyComplete() {
  try {
    localStorage.setItem("gmail-genie-has-applied", "true");
  } catch {
    /* ignore */
  }
}
