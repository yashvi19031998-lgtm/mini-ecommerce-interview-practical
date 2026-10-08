import Link from 'next/link';
import { 
  LayoutDashboard, 
  Search, 
  Users, 
  FileText, 
  Activity, 
  Globe, 
  Settings 
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  currentPath?: string;
}

const navItems = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Lead Finder', href: '/finder', icon: Search },
  { name: 'Leads', href: '/leads', icon: Users },
  { name: 'Search Queries', href: '/queries', icon: FileText },
  { name: 'Search Runs', href: '/runs', icon: Activity },
  { name: 'Sources', href: '/sources', icon: Globe },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar({ currentPath }: SidebarProps) {
  return (
    <div className="flex h-screen w-64 flex-col bg-gray-900 text-white">
      <div className="flex h-16 items-center justify-center border-b border-gray-800">
        <h1 className="text-xl font-bold text-blue-400">IT Lead Finder</h1>
      </div>
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navItems.map((item) => {
          const isActive = currentPath === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center rounded-md px-2 py-2 text-sm font-medium",
                isActive 
                  ? "bg-gray-800 text-white" 
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-5 w-5 flex-shrink-0",
                  isActive ? "text-blue-400" : "text-gray-400 group-hover:text-gray-300"
                )}
                aria-hidden="true"
              />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-gray-800">
        <div className="rounded-md bg-yellow-500/10 p-3 text-sm text-yellow-500">
          <p className="font-semibold mb-1">DEMO MODE</p>
          <p className="text-xs">Running with mock APIs and DB.</p>
        </div>
      </div>
    </div>
  );
}
