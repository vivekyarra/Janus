import React from "react";
import ReactDOM from "react-dom/client";
import { ClerkProvider, SignIn, SignUp, UserButton, useAuth } from "@clerk/react";
import App from "./App";
import "./styles.css";

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function AuthenticatedJanus() {
  const { getToken, isLoaded, isSignedIn } = useAuth({ treatPendingAsSignedOut: false });
  if (!isLoaded) {
    return (
      <main className="auth-shell">
        <div className="auth-hero-col">
          <span className="auth-kicker">JANUS CONTROL PLANE</span>
          <h1 className="auth-hero-title">Loading trust boundary.</h1>
        </div>
      </main>
    );
  }
  if (isSignedIn) return <App getAccessToken={getToken} userControl={<UserButton />} />;
  const creatingAccount = window.location.pathname === "/sign-up";
  return (
    <main className="auth-shell">
      <div className="auth-hero-col">
        <span className="auth-kicker">JANUS CONTROL PLANE</span>
        <h1 className="auth-hero-title">
          {creatingAccount ? "Create your authority profile." : "Human authority starts with identity."}
        </h1>
        <p className="auth-hero-desc">
          {creatingAccount
            ? "One verified identity owns mandate issuance, revocation, and every human step-up."
            : "Sign in before issuing, revoking, or stepping up a payment mandate."}
        </p>
      </div>
      <div className="auth-card-col">
        {creatingAccount ? (
          <SignUp routing="path" path="/sign-up" signInUrl="/" />
        ) : (
          <SignIn routing="path" path="/" signUpUrl="/sign-up" />
        )}
      </div>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {publishableKey ? (
      <ClerkProvider publishableKey={publishableKey}>
        <AuthenticatedJanus />
      </ClerkProvider>
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
