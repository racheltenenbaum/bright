import { useEffect, useRef } from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import LoginForm from "./LoginForm";
import RegisterForm from "./RegisterForm";

export default function AuthModal({ mode, redirectTo, onClose, onSwitch }) {
  const navigate = useNavigate();
  const cardRef = useRef(null);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    // Keep the page behind from scrolling while the modal is open.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  // Back to the top of the card when switching between log in / register.
  useEffect(() => {
    cardRef.current?.scrollTo({ top: 0 });
  }, [mode]);

  function handleSuccess() {
    onClose();
    if (redirectTo) navigate(redirectTo);
  }

  const Form = mode === "login" ? LoginForm : RegisterForm;

  return (
    <div
      className="auth-modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={cardRef}
        className="auth-card auth-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
      >
        <button type="button" className="auth-modal-close" onClick={onClose} aria-label="Close">
          <FontAwesomeIcon icon={faXmark} />
        </button>
        <Form onSuccess={handleSuccess} onSwitch={onSwitch} onLeave={onClose} />
      </div>
    </div>
  );
}

AuthModal.propTypes = {
  mode: PropTypes.oneOf(["login", "register"]).isRequired,
  redirectTo: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onSwitch: PropTypes.func.isRequired,
};
