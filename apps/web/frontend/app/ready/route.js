export async function GET() {
  const identityMode = process.env.HOMELAB_ANALYTICS_IDENTITY_MODE || "unconfigured";
  return Response.json({
    status: "ready",
    identity_mode: identityMode
  });
}
