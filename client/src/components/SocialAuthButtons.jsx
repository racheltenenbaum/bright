import { useState } from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faGoogle, faApple } from "@fortawesome/free-brands-svg-icons";
import { useAuth } from "../context/AuthContext";
import { track } from "../analytics";
import { signInWithGoogle, signInWithApple, isAppleSignInSupported } from "../utils/socialAuth";

export default function SocialAuthButtons({ onError }) {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [pending, setPending] = useState(null); // null | "google" | "apple"

  async function handle(provider, signInFn) {
    setPending(provider);
    onError(null);
    try {
      const data = await signInFn();
      if (!data) return; // user cancelled
      login(data.user, data.access_token);
      track(`Signed In With ${provider === "google" ? "Google" : "Apple"}`);
      navigate("/plan");
    } catch {
      onError(`Could not sign in with ${provider === "google" ? "Google" : "Apple"}. Please try again.`);
    } finally {
      setPending(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <button
        type="button"
        className="btn-outline"
        onClick={() => handle("google", signInWithGoogle)}
        disabled={pending !== null}
        style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", width: "100%" }}
      >
        <FontAwesomeIcon icon={faGoogle} />
        {pending === "google" ? "Signing in…" : "Continue with Google"}
      </button>
      {isAppleSignInSupported() && (
        <button
          type="button"
          className="btn-outline"
          onClick={() => handle("apple", signInWithApple)}
          disabled={pending !== null}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", width: "100%" }}
        >
          <FontAwesomeIcon icon={faApple} />
          {pending === "apple" ? "Signing in…" : "Continue with Apple"}
        </button>
      )}
    </div>
  );
}

SocialAuthButtons.propTypes = {
  onError: PropTypes.func.isRequired,
};
