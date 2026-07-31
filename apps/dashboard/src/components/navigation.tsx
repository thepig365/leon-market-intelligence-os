import Link from "next/link";
import { dashboardSections } from "@/lib/navigation";

export function Navigation() {
  return (
    <nav aria-label="LMIO 主导航" className="nav">
      {dashboardSections.map((section) => (
        <Link href={`/${section.slug}`} key={section.slug}>
          {section.label}
        </Link>
      ))}
    </nav>
  );
}
