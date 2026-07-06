import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../store/authStore';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { Download, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const DATE_PRESETS = [
  { label: 'Today', value: 'today' },
  { label: 'Last 24 Hours', value: '24h' },
  { label: 'Last 7 Days', value: '7d' },
  { label: 'Custom', value: 'custom' }
];

export const FleetTelemetry: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [preset, setPreset] = useState('24h');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // We could fetch devices and customers here to populate dropdowns, 
  // but for a compact interface, we will just provide basic filters.
  const [deviceId, setDeviceId] = useState('');
  const [customerId, setCustomerId] = useState('');

  const getDateRange = () => {
    const now = new Date();
    let start = new Date();
    let end = now;

    if (preset === 'today') {
      start.setHours(0, 0, 0, 0);
    } else if (preset === '24h') {
      start.setHours(start.getHours() - 24);
    } else if (preset === '7d') {
      start.setDate(start.getDate() - 7);
    } else if (preset === 'custom') {
      return { 
        start: startDate ? new Date(startDate).toISOString() : null, 
        end: endDate ? new Date(endDate).toISOString() : null 
      };
    }

    return { start: start.toISOString(), end: end.toISOString() };
  };

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['fleet_telemetry', page, preset, startDate, endDate, deviceId, customerId],
    queryFn: async () => {
      const { start, end } = getDateRange();
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '20',
      });
      if (start) params.append('start_date', start);
      if (end) params.append('end_date', end);
      if (deviceId) params.append('device_id', deviceId);
      if (customerId) params.append('customer_id', customerId);
      
      const res = await api.get(`/api/v1/telemetry?${params.toString()}`);
      return res.data;
    },
    refetchInterval: 30000
  });

  const handleExport = async () => {
    const { start, end } = getDateRange();
    const params = new URLSearchParams();
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    if (deviceId) params.append('device_id', deviceId);
    if (customerId) params.append('customer_id', customerId);

    try {
      const res = await api.get(`/api/v1/telemetry/export?${params.toString()}`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fleet_telemetry_${new Date().toISOString()}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed', error);
      alert('Failed to export data.');
    }
  };

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      <PageHeader 
        title="Fleet Telemetry"
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => refetch()}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={handleExport}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-primary-700 bg-primary-50 hover:bg-primary-100 focus:outline-none"
            >
              <Download className="h-4 w-4 mr-2" />
              Export JSON
            </button>
          </div>
        }
      />

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 flex-1 flex flex-col overflow-hidden">
        {/* Filters */}
        <div className="p-4 border-b border-gray-200 flex flex-wrap gap-4 items-center bg-gray-50">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Date Range:</label>
            <select
              value={preset}
              onChange={(e) => { setPreset(e.target.value); setPage(1); }}
              className="block w-40 pl-3 pr-10 py-1.5 text-base border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
            >
              {DATE_PRESETS.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          
          {preset === 'custom' && (
            <div className="flex items-center gap-2">
              <input 
                type="datetime-local" 
                value={startDate} 
                onChange={e => setStartDate(e.target.value)}
                className="block text-sm border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
              />
              <span className="text-gray-500">to</span>
              <input 
                type="datetime-local" 
                value={endDate} 
                onChange={e => setEndDate(e.target.value)}
                className="block text-sm border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          )}

          <div className="flex items-center gap-2">
            <input 
              type="text" 
              placeholder="Device ID (UUID)"
              value={deviceId}
              onChange={(e) => { setDeviceId(e.target.value); setPage(1); }}
              className="block w-48 text-sm border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <input 
              type="text" 
              placeholder="Customer ID (UUID)"
              value={customerId}
              onChange={(e) => { setCustomerId(e.target.value); setPage(1); }}
              className="block w-48 text-sm border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Device</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Batt %</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Signal</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Temp</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Panel V</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Chg (mA)</th>
                <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Load</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200 text-sm">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-center"><Skeleton className="h-4 w-12 mx-auto" /></td>
                  </tr>
                ))
              ) : isError ? (
                <tr><td colSpan={9} className="px-6 py-10 text-center text-red-500">Failed to load telemetry.</td></tr>
              ) : data?.items.length === 0 ? (
                <tr><td colSpan={9} className="px-6 py-10 text-center text-gray-500">No telemetry found for this range.</td></tr>
              ) : (
                data?.items.map((row: any) => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-6 py-2 whitespace-nowrap text-gray-500 font-mono">
                      {new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      <div className="text-xs text-gray-400">{new Date(row.timestamp).toLocaleDateString()}</div>
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap">
                      <div 
                        className="font-medium text-primary-600 hover:text-primary-900 cursor-pointer"
                        onClick={() => navigate(`/devices/${row.device_id}`)}
                      >
                        {row.device_name}
                      </div>
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-gray-500">
                      {row.customer_name || '—'}
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-right font-mono text-gray-900">
                      {row.battery_percentage}%
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-right font-mono text-gray-900">
                      {row.signal_strength} dBm
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-right font-mono text-gray-900">
                      {row.temperature}°C
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-right font-mono text-gray-900">
                      {row.panel_voltage}V
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-right font-mono text-gray-900">
                      {row.charging_current}
                    </td>
                    <td className="px-6 py-2 whitespace-nowrap text-center font-mono">
                      {row.light_load_status ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          ON
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                          OFF
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Showing <span className="font-medium">{((data.page - 1) * data.page_size) + 1}</span> to <span className="font-medium">{Math.min(data.page * data.page_size, data.total)}</span> of <span className="font-medium">{data.total}</span> records
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(data.total_pages, p + 1))}
                    disabled={page === data.total_pages}
                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Next
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
