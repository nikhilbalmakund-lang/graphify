import {
  Activity,
  Bell,
  Bot,
  BrainCircuit,
  CalendarClock,
  CandlestickChart,
  ChartNoAxesCombined,
  FlaskConical,
  Gauge,
  History,
  LayoutDashboard,
  LayoutGrid,
  type LucideIcon,
  Microscope,
  Newspaper,
  NotebookPen,
  Radar,
  ScanSearch,
  Settings,
  Wallet,
  Waves,
  Zap,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  keywords?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard, shortcut: "G", keywords: "home overview" },
      { href: "/markets", label: "Markets", icon: Activity, shortcut: "M", keywords: "quotes prices watchlist" },
      { href: "/chart", label: "Chart", icon: CandlestickChart, shortcut: "C", keywords: "candles indicators drawings" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/signals", label: "AI Signals", icon: Zap, shortcut: "S", keywords: "setups trades opportunities" },
      { href: "/scanner", label: "Market Scanner", icon: Radar, keywords: "opportunities screen" },
      { href: "/chart-scanner", label: "AI Chart Scanner", icon: ScanSearch, keywords: "screenshot image upload" },
      { href: "/analyst", label: "AI Analyst", icon: Bot, shortcut: "A", keywords: "chat ask question" },
      { href: "/research", label: "Research", icon: Microscope, keywords: "workspace scenarios report" },
    ],
  },
  {
    label: "Context",
    items: [
      { href: "/calendar", label: "Economic Calendar", icon: CalendarClock, keywords: "events macro nfp cpi" },
      { href: "/news", label: "News", icon: Newspaper, keywords: "headlines sentiment" },
      { href: "/heatmap", label: "Heatmap", icon: LayoutGrid, keywords: "performance grid" },
      { href: "/psychology", label: "Market Psychology", icon: Waves, keywords: "risk on off breadth correlation" },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/strategy-lab", label: "Strategy Lab", icon: FlaskConical, keywords: "strategies regimes ml calibration" },
      { href: "/backtesting", label: "Backtesting", icon: History, shortcut: "B", keywords: "backtest walk forward" },
      { href: "/analytics", label: "Analytics", icon: ChartNoAxesCombined, keywords: "performance model ai stats" },
    ],
  },
  {
    label: "Trading",
    items: [
      { href: "/paper-trading", label: "Paper Trading", icon: Gauge, shortcut: "P", keywords: "orders positions simulated" },
      { href: "/portfolio", label: "Portfolio", icon: Wallet, keywords: "equity exposure balance" },
      { href: "/journal", label: "Trade Journal", icon: NotebookPen, keywords: "trades log notes" },
      { href: "/alerts", label: "Alerts", icon: Bell, keywords: "notifications price level" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/status", label: "System Status", icon: BrainCircuit, keywords: "health connections providers" },
      { href: "/settings", label: "Settings", icon: Settings, keywords: "api keys risk appearance" },
    ],
  },
];

export const ALL_NAV: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
