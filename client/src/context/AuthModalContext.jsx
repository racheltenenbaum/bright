import { createContext, useCallback, useContext, useMemo, useState } from "react";
import PropTypes from "prop-types";
import AuthModal from "../components/AuthModal";

const AuthModalContext = createContext(null);

// Log in / register live in one dismissible modal opened over whatever page
// the user is on, rather than on pages of their own — so being asked to log
// in (e.g. to save a route) never navigates away from what they were doing.
// redirectTo is only for callers that genuinely need to land somewhere after
// success (a protected page the user was trying to reach).
export function AuthModalProvider({ children }) {
  const [state, setState] = useState({ mode: null, redirectTo: null });

  const openAuth = useCallback((mode, { redirectTo = null } = {}) => {
    setState({ mode, redirectTo });
  }, []);
  const closeAuth = useCallback(() => {
    setState({ mode: null, redirectTo: null });
  }, []);
  const switchMode = useCallback(() => {
    setState((s) => ({ ...s, mode: s.mode === "login" ? "register" : "login" }));
  }, []);

  const value = useMemo(() => ({ openAuth, closeAuth }), [openAuth, closeAuth]);

  return (
    <AuthModalContext.Provider value={value}>
      {children}
      {state.mode && (
        <AuthModal
          mode={state.mode}
          redirectTo={state.redirectTo}
          onClose={closeAuth}
          onSwitch={switchMode}
        />
      )}
    </AuthModalContext.Provider>
  );
}

AuthModalProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useAuthModal() {
  return useContext(AuthModalContext);
}
