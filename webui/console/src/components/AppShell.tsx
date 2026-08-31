import { HeaderBar, type ConsoleView } from "./HeaderBar";

interface AppShellProps {
  view: ConsoleView;
  onChangeView: (view: ConsoleView) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  scanning: boolean;
  scanStatusLabel?: string;
  scanProgressPercent?: number;
  scanFindingCount?: number;
  scanDisabled?: boolean;
  onToggleScan: () => void;
  targets?: { id: string; label: string; ready?: boolean }[];
  selectedTarget?: string;
  onSelectTarget?: (id: string) => void;
  children: React.ReactNode;
}

export function AppShell({ children, ...header }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col bg-canvas text-foreground">
      <HeaderBar {...header} />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
