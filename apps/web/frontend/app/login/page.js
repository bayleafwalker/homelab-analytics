export default function LoginPage({ searchParams }) {
  const error = searchParams?.error;
  return (
    <main className="loginPage">
      <section className="panel loginCard">
        <div className="eyebrow">Bootstrap Local Auth</div>
        <h1>Sign In</h1>
        <p className="lede">
          This frontend only consumes the API. Local auth is a bootstrap path until
          OIDC replaces it.
        </p>
        {error ? (
          <div className="errorBanner">Invalid username or password.</div>
        ) : null}
        <form className="loginForm" action="/auth/login" method="post">
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" name="username" type="text" autoComplete="username" required />
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
      </section>
    </main>
  );
}
