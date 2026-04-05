export async function GET() {
  return new Response("homelab_analytics_web_up 1\n", {
    headers: {
      "content-type": "text/plain; version=0.0.4"
    }
  });
}
