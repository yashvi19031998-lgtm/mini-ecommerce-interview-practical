"use client";

import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { supabase } from '@/lib/supabase';

export default function SearchQueriesPage() {
  const [queries, setQueries] = useState<any[]>([]);

  useEffect(() => {
    async function fetchQueries() {
      const { data } = await supabase.from('search_queries').select('*').order('created_at', { ascending: false });
      if (data) setQueries(data);
    }
    fetchQueries();
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Search Queries</h1>
        <button className="inline-flex items-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700">
          <Plus className="mr-2 h-4 w-4" />
          Add Query
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Query</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Platform</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {queries.map((q) => (
              <tr key={q.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{q.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500 font-mono max-w-xs truncate">{q.query}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{q.platform}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${q.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {q.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
