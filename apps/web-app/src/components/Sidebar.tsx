"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  Upload,
  Scale,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Trang chủ", icon: LayoutDashboard },
  { href: "/review", label: "Rà soát hợp đồng", icon: FileText },
  { href: "/chat", label: "Tư vấn pháp lý", icon: MessageSquare },
  { href: "/ingest", label: "Nhập liệu (Quản trị)", icon: Upload },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-sidebar flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
            <Scale className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg leading-tight">
              AI Pháp lý
            </h1>
            <p className="text-muted-foreground text-xs">
              Rà soát Hợp đồng Việt Nam
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? "bg-primary text-white"
                      : "text-sidebar-foreground hover:bg-slate-700"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-muted-foreground">
          <p>AI Rà soát Hợp đồng Pháp lý Việt Nam</p>
          <p className="mt-1">v0.1.0</p>
        </div>
      </div>
    </aside>
  );
}
