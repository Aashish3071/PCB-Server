import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../store/authStore';
import { PageHeader } from '../components/ui/PageHeader';
import { Card } from '../components/ui/Card';
import { Skeleton } from '../components/ui/Skeleton';
import { Cpu, Wifi, WifiOff, AlertTriangle, Users, Activity } from 'lucide-react';

interface DashboardSummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  active_alerts: number;
  total_customers: number;
  last_telemetry_timestamp: string | null;
}

const fetchDashboardSummary = async (): Promise<DashboardSummary> => {
  const { data } = await api.get('/api/v1/dashboard/summary');
  return data;
};

export const Dashboard: React.FC = () => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard_summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30000, // Refresh every 30s
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <PageHeader 
        title="Dashboard" 
        description="Operational overview of your device fleet."
      />

      {isError && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-md mb-6">
          <p className="text-sm text-red-700">Failed to load dashboard metrics. Please check your connection.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {/* Total Devices */}
        <Card to="/devices" className="p-5 flex items-center">
          <div className="rounded-md bg-blue-50 p-3">
            <Cpu className="h-6 w-6 text-blue-600" />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">Total Devices</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : (
              <p className="text-2xl font-semibold text-gray-900">{data?.total_devices}</p>
            )}
          </div>
        </Card>

        {/* Online Devices */}
        <Card to="/devices?status=online" className="p-5 flex items-center">
          <div className="rounded-md bg-green-50 p-3">
            <Wifi className="h-6 w-6 text-green-600" />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">Online</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : (
              <p className="text-2xl font-semibold text-gray-900">{data?.online_devices}</p>
            )}
          </div>
        </Card>

        {/* Offline Devices */}
        <Card to="/devices?status=offline" className="p-5 flex items-center">
          <div className="rounded-md bg-gray-100 p-3">
            <WifiOff className="h-6 w-6 text-gray-500" />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">Offline</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : (
              <p className="text-2xl font-semibold text-gray-900">{data?.offline_devices}</p>
            )}
          </div>
        </Card>

        {/* Active Alerts */}
        <Card to="/alerts?status=active" className="p-5 flex items-center border-l-4 border-l-red-500">
          <div className="rounded-md bg-red-50 p-3">
            <AlertTriangle className="h-6 w-6 text-red-600" />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">Active Alerts</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : (
              <p className="text-2xl font-semibold text-gray-900">{data?.active_alerts}</p>
            )}
          </div>
        </Card>

        {/* Total Customers */}
        <Card to="/customers" className="p-5 flex items-center">
          <div className="rounded-md bg-purple-50 p-3">
            <Users className="h-6 w-6 text-purple-600" />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">Customers</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : (
              <p className="text-2xl font-semibold text-gray-900">{data?.total_customers}</p>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-8">
        <Card className="p-6">
          <div className="flex items-center text-gray-500">
            <Activity className="h-5 w-5 mr-2 text-primary-500" />
            <span className="text-sm font-medium">Last Telemetry Received:</span>
            {isLoading ? (
              <Skeleton className="h-5 w-32 ml-3" />
            ) : (
              <span className="ml-3 text-sm text-gray-900 font-mono">
                {data?.last_telemetry_timestamp 
                  ? new Date(data.last_telemetry_timestamp).toLocaleString() 
                  : 'No telemetry data yet'}
              </span>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};
