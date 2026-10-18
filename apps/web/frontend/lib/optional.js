// Optional panels must not take a whole board down: a failed or missing
// adapter resolves to the panel's fallback (its empty state). Auth redirects
// still propagate so an expired session goes to /login.
export async function optional(promise, fallback) {
  try {
    return await promise;
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")) {
      throw error;
    }
    return fallback;
  }
}
