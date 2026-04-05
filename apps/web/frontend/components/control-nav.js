import Link from "next/link";

const CONTROL_ITEMS = [
  { href: "/control", label: "Security" },
  { href: "/control/catalog", label: "Catalog" },
  { href: "/control/execution", label: "Execution" }
];

export function ControlNav({ currentPath }) {
  return (
    <nav className="subnav" aria-label="Control plane sections">
      {CONTROL_ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="subnavLink"
          data-active={currentPath === item.href}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
