import { HeaderBar, type HeaderBarProps } from "./HeaderBar";

/**
 * The shell owns the chrome and forwards every header control unchanged.
 *
 * The props were duplicated from `HeaderBarProps` and drifted whenever a
 * control was added, so they are derived from it instead.
 */
type AppShellProps = HeaderBarProps & { children: React.ReactNode };

export function AppShell({ children, ...header }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col bg-canvas text-foreground">
      <HeaderBar {...header} />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
