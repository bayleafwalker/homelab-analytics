const IDENTITY_MODE = process.env.HOMELAB_ANALYTICS_IDENTITY_MODE || "disabled";

function errorMessageFor(error, identityMode) {
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
  if (error && identityMode === "oidc") {
    return "Single sign-on failed. Try again or contact an administrator.";
  }
  if (error) {
    return "Invalid username or password.";
  }
  return "";
}

export default function LoginPage({ searchParams }) {
  const error = searchParams?.error;
  const identityMode = IDENTITY_MODE.toLowerCase();
  const isOidc = identityMode === "oidc";
  const isProxy = identityMode === "proxy";
  const errorMessage = errorMessageFor(error, identityMode);

  return (
    <main className="loginPage">
      <section className="panel loginCard">
        <div className="eyebrow">
          {isOidc
            ? "OIDC Single Sign-On"
            : isProxy
              ? "Proxy-Managed Sign-In"
            : identityMode === "local_single_user"
              ? "Break-Glass Local Auth"
              : "Bootstrap Local Auth"}
        </div>
        <h1>Sign In</h1>
        <p className="lede">
          {isOidc
            ? "This frontend only consumes the API. Sign in through your configured OIDC provider."
            : isProxy
              ? "This deployment trusts upstream proxy identity headers. Authenticate through your ingress proxy."
            : identityMode === "local_single_user"
              ? "This frontend only consumes the API. Local auth is running in temporary break-glass mode."
              : "This frontend only consumes the API. Local auth remains available for bootstrap and break-glass access."}
        </p>
        {errorMessage ? <div className="errorBanner">{errorMessage}</div> : null}
        {isOidc ? (
          <a className="primaryButton" href="/auth/login">
            Sign In with OIDC
          </a>
        ) : isProxy ? (
          <p className="lede">
            No direct login form is available in proxy mode.
          </p>
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
