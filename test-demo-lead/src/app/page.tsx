import { Users, FileText, CheckCircle, Search, Globe, AlertTriangle } from 'lucide-react';

const stats = [
  { name: 'Total Leads', value: '142', icon: Users, color: 'text-blue-500', bg: 'bg-blue-100' },
  { name: 'New Leads', value: '28', icon: FileText, color: 'text-green-500', bg: 'bg-green-100' },
  { name: 'Qualified Leads', value: '85', icon: CheckCircle, color: 'text-purple-500', bg: 'bg-purple-100' },
  { name: 'High Quality', value: '41', icon: AlertTriangle, color: 'text-yellow-500', bg: 'bg-yellow-100' },
  { name: 'URLs Processed', value: '1,024', icon: Globe, color: 'text-gray-500', bg: 'bg-gray-100' },
  { name: 'AI Direct', value: '850', icon: Search, color: 'text-indigo-500', bg: 'bg-indigo-100' },
  { name: 'Decodo Fallback', value: '174', icon: Search, color: 'text-orange-500', bg: 'bg-orange-100' },
];

export default function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Dashboard</h1>
      
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {stats.map((item) => (
          <div key={item.name} className="overflow-hidden rounded-lg bg-white shadow">
            <div className="p-5">
              <div className="flex items-center">
                <div className={`flex-shrink-0 rounded-md p-3 ${item.bg}`}>
                  <item.icon className={`h-6 w-6 ${item.color}`} aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="truncate text-sm font-medium text-gray-500">{item.name}</dt>
                    <dd>
                      <div className="text-lg font-medium text-gray-900">{item.value}</div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Leads</h2>
        <div className="overflow-hidden bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6 text-center text-gray-500">
            <p>Recent leads will appear here.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
