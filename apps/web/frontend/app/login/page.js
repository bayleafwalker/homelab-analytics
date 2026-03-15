const AUTH_MODE = process.env.HOMELAB_ANALYTICS_AUTH_MODE || "disabled";

function errorMessageFor(error, authMode) {
  if (error === "locked-out") {
    return "Too many failed login attempts. Try again later.";
  }
  if (error === "invalid-credentials") {
    return "Invalid username or password.";
  }
  if (error === "oidc-unmapped") {
    return "Your OIDC identity is valid but not mapped to an application role.";
  }
  if (error === "oidc-failed") {
    return "Single sign-on failed. Try again or contact an administrator.";
  }
  if (error && authMode === "oidc") {
    return "Single sign-on failed. Try again or contact an administrator.";
  }
  if (error) {
    return "Invalid username or password.";
  }
  return "";
}

export default function LoginPage({ searchParams }) {
  const error = searchParams?.error;
  const authMode = AUTH_MODE.toLowerCase();
  const errorMessage = errorMessageFor(error, authMode);

  return (
    <main className="loginPage">
      <section className="panel loginCard">
        <div className="eyebrow">
          {authMode === "oidc" ? "OIDC Single Sign-On" : "Bootstrap Local Auth"}
        </div>
        <h1>Sign In</h1>
        <p className="lede">
          {authMode === "oidc"
            ? "This frontend only consumes the API. Sign in through your configured OIDC provider."
            : "This frontend only consumes the API. Local auth remains available for bootstrap and break-glass access."}
        </p>
        {errorMessage ? <div className="errorBanner">{errorMessage}</div> : null}
        {authMode === "oidc" ? (
          <a className="primaryButton" href="/auth/login">
            Sign In with OIDC
          </a>
        ) : (
          <form className="loginForm" action="/auth/login" method="post">
            <div className="field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </div>
            <button className="primaryButton" type="submit">
              Sign In
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
