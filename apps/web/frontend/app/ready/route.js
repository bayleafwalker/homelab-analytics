export async function GET() {
  return Response.json({
    status: "ready",
    auth_mode: process.env.HOMELAB_ANALYTICS_AUTH_MODE || "disabled"
  });
}
