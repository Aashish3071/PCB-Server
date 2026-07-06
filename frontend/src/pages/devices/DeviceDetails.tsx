import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../store/authStore';
import { PageHeader } from '../../components/ui/PageHeader';
import { Badge } from '../../components/ui/Badge';
import { Skeleton } from '../../components/ui/Skeleton';
import { 
  ChevronRight, 
  Download, 
  RefreshCw,
  Battery,
  Wifi,
  Thermometer,
  Droplets,
  Sun,
  Zap,
  Lightbulb,
  Clock,
  Activity,
  AlertTriangle
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const DeviceDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [telemetryPage, setTelemetryPage] = useState(1);
  const telemetryPageSize = 10;

  // Overview Query (Auto-refreshes every 30 seconds)
  const { 
    data: overview, 
    isLoading: isOverviewLoading, 
    isError: isOverviewError,
    refetch: refetchOverview,
    isRefetching: isOverviewRefetching
  } = useQuery({
    queryKey: ['device_overview', id],
    queryFn: async () => {
      const res = await api.get(`/api/v1/devices/${id}/overview`);
      return res.data;
    },
    refetchInterval: 30000 // 30 seconds auto-refresh
  });

  // Telemetry History Query
  const {
    data: telemetryPageData,
    isLoading: isTelemetryLoading
  } = useQuery({
    queryKey: ['device_telemetry', id, telemetryPage],
    queryFn: async () => {
      const res = await api.get(`/api/v1/devices/${id}/telemetry?page=${telemetryPage}&page_size=${telemetryPageSize}`);
      return res.data;
    }
  });

  const handleExport = async () => {
    try {
      const res = await api.get(`/api/v1/devices/${id}/export`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `device_${overview?.device?.device_uid || id}_export.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      console.error('Export failed', e);
      alert('Failed to export data');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ONLINE': return <Badge variant="success" dot>Online</Badge>;
      case 'OFFLINE': return <Badge variant="neutral" dot>Offline</Badge>;
      case 'DISABLED': return <Badge variant="error" dot>Disabled</Badge>;
      case 'PROVISIONED': return <Badge variant="primary" dot>Provisioned</Badge>;
      default: return <Badge variant="neutral">{status}</Badge>;
    }
  };

  const getAlertSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return <Badge variant="error">Critical</Badge>;
      case 'WARNING': return <Badge variant="warning">Warning</Badge>;
      case 'INFO': return <Badge variant="primary">Info</Badge>;
      default: return <Badge variant="neutral">{severity}</Badge>;
    }
  };

  if (isOverviewLoading) {
    return <div className="p-6"><Skeleton className="h-8 w-64 mb-6" /><Skeleton className="h-64 w-full" /></div>;
  }

  if (isOverviewError || !overview) {
    return <div className="p-6 text-red-500">Failed to load device details.</div>;
  }

  const { device, latest_telemetry: t, analytics, recent_alerts } = overview;

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Breadcrumbs */}
      <nav className="flex text-sm text-gray-500 font-medium" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-2">
          <li><Link to="/" className="hover:text-gray-900">Dashboard</Link></li>
          <li><ChevronRight className="w-4 h-4 text-gray-400" /></li>
          <li><Link to="/devices" className="hover:text-gray-900">Devices</Link></li>
          <li><ChevronRight className="w-4 h-4 text-gray-400" /></li>
          <li className="text-gray-900 font-mono" aria-current="page">{device.device_uid}</li>
        </ol>
      </nav>

      <PageHeader 
        title={
          <div className="flex items-center space-x-3">
            <span>{device.device_name}</span>
            {getStatusBadge(device.status)}
          </div>
        }
        actions={
          <div className="flex items-center space-x-3">
            <button
              onClick={() => refetchOverview()}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isOverviewRefetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={handleExport}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
            >
              <Download className="h-4 w-4 mr-2 text-gray-500" />
              Export JSON
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Section 1: Device Information */}
        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-gray-500" />
            Device Information
          </h3>
          <dl className="grid grid-cols-1 gap-y-3 text-sm">
            <div className="flex justify-between border-b border-gray-100 pb-2">
              <dt className="text-gray-500">Device UID</dt>
              <dd className="font-mono text-gray-900">{device.device_uid}</dd>
            </div>
            <div className="flex justify-between border-b border-gray-100 pb-2">
              <dt className="text-gray-500">Customer</dt>
              <dd className="text-gray-900">{device.customer_name || 'Unassigned'}</dd>
            </div>
            <div className="flex justify-between border-b border-gray-100 pb-2">
              <dt className="text-gray-500">Location</dt>
              <dd className="text-gray-900">{device.installation_location || '—'}</dd>
            </div>
            <div className="flex justify-between border-b border-gray-100 pb-2">
              <dt className="text-gray-500">Firmware</dt>
              <dd className="text-gray-900">{device.firmware_version || '—'}</dd>
            </div>
            <div className="flex justify-between pb-2">
              <dt className="text-gray-500">Created At</dt>
              <dd className="text-gray-900">{new Date(device.created_at).toLocaleDateString()}</dd>
            </div>
          </dl>
        </div>

        {/* Section 2: Current Sensors */}
        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200 lg:col-span-2">
          <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-gray-500" />
            Current Sensor Values
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Battery className="w-3 h-3 mr-1 text-gray-400"/> Battery %</span>
              <span className="text-lg font-semibold text-gray-900">{t?.battery_percentage ?? '—'}%</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Wifi className="w-3 h-3 mr-1 text-gray-400"/> Signal</span>
              <span className="text-lg font-semibold text-gray-900">{t?.signal_strength ?? '—'} dBm</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Thermometer className="w-3 h-3 mr-1 text-gray-400"/> Temp</span>
              <span className="text-lg font-semibold text-gray-900">{t?.temperature ?? '—'}°C</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Droplets className="w-3 h-3 mr-1 text-gray-400"/> Humidity</span>
              <span className="text-lg font-semibold text-gray-900">{t?.humidity ?? '—'}%</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Sun className="w-3 h-3 mr-1 text-gray-400"/> Panel V</span>
              <span className="text-lg font-semibold text-gray-900">{t?.panel_voltage ?? '—'}V</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Zap className="w-3 h-3 mr-1 text-gray-400"/> Battery V</span>
              <span className="text-lg font-semibold text-gray-900">{t?.battery_voltage ?? '—'}V</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Zap className="w-3 h-3 mr-1 text-gray-400"/> Charge Curr</span>
              <span className="text-lg font-semibold text-gray-900">{t?.charging_current ?? '—'}A</span>
            </div>
            <div className="flex flex-col border border-gray-100 p-3 rounded-md bg-gray-50">
              <span className="text-xs text-gray-500 flex items-center mb-1"><Lightbulb className="w-3 h-3 mr-1 text-gray-400"/> Light Load</span>
              <span className="text-lg font-semibold text-gray-900">{t?.light_load_status ? 'ON' : 'OFF'}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Section 3: Analytics & Trend */}
        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200 lg:col-span-2 flex flex-col">
          <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-gray-500" />
            24h Analytics & Battery Trend
          </h3>
          <div className="flex flex-col md:flex-row gap-4 flex-1">
            <div className="flex-1 min-h-[200px]">
              {analytics.battery_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analytics.battery_trend}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} 
                      tick={{fontSize: 10}} 
                      stroke="#9CA3AF"
                    />
                    <YAxis domain={[0, 100]} tick={{fontSize: 10}} stroke="#9CA3AF" />
                    <Tooltip 
                      labelFormatter={(l) => new Date(l).toLocaleString()}
                      contentStyle={{borderRadius: '0.375rem', border: '1px solid #E5E7EB', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'}}
                    />
                    <Line type="monotone" dataKey="battery_percentage" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="w-full h-full flex items-center justify-center text-sm text-gray-400 border border-dashed border-gray-200 rounded-md">
                  No telemetry in the last 24 hours.
                </div>
              )}
            </div>
            <div className="w-full md:w-48 flex flex-col gap-2">
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100">
                <span className="text-xs text-gray-500">Current Battery</span>
                <span className="font-semibold text-sm">{t?.battery_percentage ?? '—'}%</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100">
                <span className="text-xs text-gray-500">Avg Battery</span>
                <span className="font-semibold text-sm">{analytics.battery_avg != null ? Math.round(analytics.battery_avg) : '—'}%</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100">
                <span className="text-xs text-gray-500">Max Battery</span>
                <span className="font-semibold text-sm">{analytics.battery_max != null ? Math.round(analytics.battery_max) : '—'}%</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100">
                <span className="text-xs text-gray-500">Min Battery</span>
                <span className="font-semibold text-sm">{analytics.battery_min != null ? Math.round(analytics.battery_min) : '—'}%</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100">
                <span className="text-xs text-gray-500">24h Data Count</span>
                <span className="font-semibold text-sm">{analytics.daily_data_count}</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-gray-50 rounded-md border border-gray-100 mt-auto">
                <span className="text-xs text-gray-500 flex items-center"><Clock className="w-3 h-3 mr-1"/> Uptime</span>
                <span className="font-semibold text-sm">{analytics.uptime_seconds != null ? `${(analytics.uptime_seconds / 3600).toFixed(1)}h` : '—'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 4: Recent Alerts */}
        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center">
            <AlertTriangle className="w-4 h-4 mr-2 text-gray-500" />
            Recent Alerts
          </h3>
          <div className="flex flex-col gap-2 h-[200px] overflow-y-auto">
            {recent_alerts.length === 0 ? (
              <div className="text-sm text-gray-500 text-center mt-8">No recent alerts.</div>
            ) : (
              recent_alerts.map((alert: any) => (
                <div key={alert.id} className={`p-3 rounded-md border text-sm flex flex-col ${alert.is_resolved ? 'bg-gray-50 border-gray-100 text-gray-500' : 'bg-white border-gray-200'}`}>
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold text-gray-900">{alert.alert_type.replace('_', ' ')}</span>
                    {getAlertSeverityBadge(alert.severity)}
                  </div>
                  <span className="text-gray-600 mb-1">{alert.message}</span>
                  <div className="flex justify-between items-center text-xs mt-1">
                    <span>{new Date(alert.created_at).toLocaleString()}</span>
                    {alert.is_resolved && <span className="text-green-600 font-medium text-xs">Resolved</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Section 5: Telemetry History */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
          <h3 className="text-sm font-medium text-gray-900 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-gray-500" />
            Telemetry History
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-white">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Battery</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Signal</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Temp</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Humidity</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Panel V</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Load</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isTelemetryLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-4 py-3 whitespace-nowrap"><Skeleton className="h-4 w-full" /></td>
                  </tr>
                ))
              ) : telemetryPageData?.items.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-sm text-gray-500">No telemetry recorded yet.</td></tr>
              ) : (
                telemetryPageData?.items.map((row: any) => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{new Date(row.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.battery_percentage ?? '—'}%</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.signal_strength ?? '—'} dBm</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.temperature ?? '—'}°C</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.humidity ?? '—'}%</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.panel_voltage ?? '—'}V</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{row.light_load_status ? 'ON' : 'OFF'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {telemetryPageData && telemetryPageData.total_pages > 1 && (
          <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div className="flex-1 flex justify-between sm:hidden">
              <button
                onClick={() => setTelemetryPage(p => Math.max(1, p - 1))}
                disabled={telemetryPage === 1}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Previous
              </button>
              <button
                onClick={() => setTelemetryPage(p => Math.min(telemetryPageData.total_pages, p + 1))}
                disabled={telemetryPage === telemetryPageData.total_pages}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Next
              </button>
            </div>
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Showing <span className="font-medium">{((telemetryPageData.page - 1) * telemetryPageData.page_size) + 1}</span> to <span className="font-medium">{Math.min(telemetryPageData.page * telemetryPageData.page_size, telemetryPageData.total)}</span> of <span className="font-medium">{telemetryPageData.total}</span> records
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                  <button
                    onClick={() => setTelemetryPage(p => Math.max(1, p - 1))}
                    disabled={telemetryPage === 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setTelemetryPage(p => Math.min(telemetryPageData.total_pages, p + 1))}
                    disabled={telemetryPage === telemetryPageData.total_pages}
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
