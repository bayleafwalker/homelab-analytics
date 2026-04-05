import "./globals.css";

export const metadata = {
  title: "Homelab Analytics",
  description: "API-backed household and homelab analytics dashboard."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
