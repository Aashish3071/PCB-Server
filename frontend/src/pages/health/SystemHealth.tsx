import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../store/authStore';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { Activity, Database, Server, Clock, GitCommit } from 'lucide-react';

export const SystemHealth: React.FC = () => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['system-health'],
    queryFn: async () => {
      const res = await api.get('/api/v1/health');
      return res.data;
    },
    refetchInterval: 30000
  });

  const getStatusColor = (status: string) => {
    return status === 'ok' ? 'bg-green-500' : 'bg-red-500';
  };

  const getStatusText = (status: string) => {
    return status === 'ok' ? 'Operational' : 'Failing';
  };

  const formatTimeAgo = (isoDate: string | null) => {
    if (!isoDate) return 'Never';
    const date = new Date(isoDate);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  };

  return (
    <div className="w-full h-full flex flex-col space-y-4 max-w-7xl mx-auto">
      <PageHeader 
        title="System Health"
        actions={
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
          >
            Refresh Status
          </button>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
              <div className="p-5">
                <Skeleton className="h-6 w-3/4 mb-4" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <Activity className="h-5 w-5 text-red-400" aria-hidden="true" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">
                Error connecting to the backend service. The API may be down.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Backend Status */}
          <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Server className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Backend Service</dt>
                    <dd className="flex items-center mt-1">
                      <span className={`h-2.5 w-2.5 rounded-full ${getStatusColor(data?.backend_status)} mr-2`} />
                      <div className="text-lg font-semibold text-gray-900">
                        {getStatusText(data?.backend_status)}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          {/* Database Status */}
          <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Database className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Database (PostgreSQL)</dt>
                    <dd className="flex items-center mt-1">
                      <span className={`h-2.5 w-2.5 rounded-full ${getStatusColor(data?.database_status)} mr-2`} />
                      <div className="text-lg font-semibold text-gray-900">
                        {getStatusText(data?.database_status)}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          {/* Telemetry Lag */}
          <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Clock className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Last Telemetry Received</dt>
                    <dd className="flex items-center mt-1">
                      <div className="text-lg font-semibold text-gray-900">
                        {formatTimeAgo(data?.last_telemetry_received)}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          {/* Versions */}
          <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <GitCommit className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">API Version</dt>
                    <dd className="flex items-center mt-1">
                      <div className="text-lg font-semibold text-gray-900 font-mono">
                        v{data?.api_version}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <GitCommit className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Frontend Version</dt>
                    <dd className="flex items-center mt-1">
                      <div className="text-lg font-semibold text-gray-900 font-mono">
                        v{data?.frontend_version}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  );
};
