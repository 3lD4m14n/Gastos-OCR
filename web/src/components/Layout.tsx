import { LayoutDashboard, LogOut, ReceiptText, Tags } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "react-oidc-context";

import { Button } from "@/components/ui/button";
import { signOut } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Inicio", icon: LayoutDashboard },
  { to: "/gastos", label: "Gastos", icon: ReceiptText },
  { to: "/categorias", label: "Categorías", icon: Tags },
];

export function Layout() {
  const auth = useAuth();
  const profile = auth.user?.profile;
  return (
    <div className="min-h-dvh bg-muted/40 pb-20 md:pb-8">
      <header className="sticky top-0 z-10 border-b bg-background">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-6 px-4">
          <span className="font-semibold">Gastos</span>
          <nav aria-label="Principal" className="hidden gap-1 md:flex">
            {LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground",
                    isActive && "bg-muted font-medium text-foreground",
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            <span className="hidden truncate text-sm text-muted-foreground sm:block">
              {profile?.name ?? profile?.email}
            </span>
            <Button variant="ghost" size="sm" onClick={() => void signOut(auth)}>
              <LogOut aria-hidden />
              Salir
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto grid max-w-4xl grid-cols-1 gap-4 p-4">
        <Outlet />
      </main>
      <nav
        aria-label="Principal, móvil"
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-3 border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 py-2 text-xs text-muted-foreground",
                isActive && "font-medium text-primary",
              )
            }
          >
            <Icon aria-hidden className="size-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
