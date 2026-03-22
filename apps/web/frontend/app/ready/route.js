export async function GET() {
  const identityMode = process.env.HOMELAB_ANALYTICS_IDENTITY_MODE;
  const authMode = process.env.HOMELAB_ANALYTICS_AUTH_MODE || "disabled";
  return Response.json({
    status: "ready",
    auth_mode: authMode,
    identity_mode: identityMode || authMode
  });
}
