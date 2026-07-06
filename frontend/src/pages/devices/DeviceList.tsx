import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../store/authStore';
import { PageHeader } from '../../components/ui/PageHeader';
import { Badge } from '../../components/ui/Badge';
import { Skeleton } from '../../components/ui/Skeleton';
import { Search, Plus, MoreVertical, RefreshCw, Battery, Wifi } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { 
  AddDeviceModal, 
  EditDeviceModal, 
  AssignCustomerModal, 
  ConfirmActionModal 
} from './DeviceModals';

// Utility for relative time
function getRelativeTime(timestamp: string | null): string {
  if (!timestamp) return 'Never';
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const daysDifference = Math.round((new Date(timestamp).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
  const hoursDifference = Math.round((new Date(timestamp).getTime() - new Date().getTime()) / (1000 * 60 * 60));
  const minsDifference = Math.round((new Date(timestamp).getTime() - new Date().getTime()) / (1000 * 60));
  
  if (Math.abs(daysDifference) > 0) return rtf.format(daysDifference, 'day');
  if (Math.abs(hoursDifference) > 0) return rtf.format(hoursDifference, 'hour');
  return rtf.format(minsDifference, 'minute');
}

export const DeviceList: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState('desc');

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editModalDevice, setEditModalDevice] = useState<any>(null);
  const [assignCustomerDevice, setAssignCustomerDevice] = useState<any>(null);
  const [confirmAction, setConfirmAction] = useState<{ action: 'DISABLE' | 'ENABLE' | 'DELETE', device: any } | null>(null);

  // Debounce search
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(handler);
  }, [search]);

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['devices', page, debouncedSearch, statusFilter, sort, order],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '20',
        sort,
        order
      });
      if (debouncedSearch) params.append('q', debouncedSearch);
      if (statusFilter) params.append('status', statusFilter);
      
      const res = await api.get(`/api/v1/devices?${params.toString()}`);
      return res.data;
    }
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ONLINE': return <Badge variant="success" dot>Online</Badge>;
      case 'OFFLINE': return <Badge variant="neutral" dot>Offline</Badge>;
      case 'DISABLED': return <Badge variant="error" dot>Disabled</Badge>;
      case 'PROVISIONED': return <Badge variant="primary" dot>Provisioned</Badge>;
      default: return <Badge variant="neutral">{status}</Badge>;
    }
  };

  const getBatteryColor = (percentage: number | null) => {
    if (percentage === null) return 'text-gray-400';
    if (percentage > 50) return 'text-green-500';
    if (percentage > 20) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getSignalColor = (signal: number | null) => {
    if (signal === null) return 'text-gray-400';
    if (signal > -70) return 'text-green-500';
    if (signal > -90) return 'text-yellow-500';
    return 'text-red-500';
  };

  // Actions Dropdown state per row
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      <PageHeader 
        title="Devices"
        actions={
          <>
            <button
              onClick={() => refetch()}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Device
            </button>
          </>
        }
      />

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 flex-1 flex flex-col overflow-hidden">
        {/* Filters */}
        <div className="p-4 border-b border-gray-200 flex flex-col sm:flex-row gap-4 items-center justify-between bg-gray-50">
          <div className="relative w-full sm:max-w-md">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Search UID, Name, or Customer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
          </div>
          <div className="flex gap-4 w-full sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="block w-full sm:w-40 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
            >
              <option value="">All Statuses</option>
              <option value="ONLINE">Online</option>
              <option value="OFFLINE">Offline</option>
              <option value="DISABLED">Disabled</option>
              <option value="PROVISIONED">Provisioned</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Device UID</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => { setSort('device_name'); setOrder(order === 'desc' ? 'asc' : 'desc'); }}>
                  Device Name {sort === 'device_name' && (order === 'desc' ? '↓' : '↑')}
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Battery</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Signal</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => { setSort('last_seen_at'); setOrder(order === 'desc' ? 'asc' : 'desc'); }}>
                  Last Seen {sort === 'last_seen_at' && (order === 'desc' ? '↓' : '↑')}
                </th>
                <th scope="col" className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-6 w-20 rounded-full" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-6 py-4 whitespace-nowrap"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"><Skeleton className="h-5 w-5 ml-auto" /></td>
                  </tr>
                ))
              ) : isError ? (
                <tr><td colSpan={8} className="px-6 py-10 text-center text-red-500">Failed to load devices.</td></tr>
              ) : data?.items.length === 0 ? (
                <tr><td colSpan={8} className="px-6 py-10 text-center text-gray-500">No devices found.</td></tr>
              ) : (
                data?.items.map((device: any) => (
                  <tr 
                    key={device.id} 
                    className="hover:bg-gray-50 group cursor-pointer"
                    onClick={() => navigate(`/devices/${device.id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(device.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-600">
                      {device.device_uid}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {device.device_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {device.customer_name || '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <Battery className={`w-4 h-4 mr-1 ${getBatteryColor(device.battery_percentage)}`} />
                        {device.battery_percentage !== null ? `${device.battery_percentage}%` : '—'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <Wifi className={`w-4 h-4 mr-1 ${getSignalColor(device.signal_strength)}`} />
                        {device.signal_strength !== null ? `${device.signal_strength} dBm` : '—'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {getRelativeTime(device.last_seen_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium relative">
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenDropdownId(openDropdownId === device.id ? null : device.id);
                        }}
                        className="text-gray-400 hover:text-gray-600 focus:outline-none p-1 rounded-full hover:bg-gray-100"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      {/* Dropdown Menu */}
                      {openDropdownId === device.id && (
                        <>
                          <div 
                            className="fixed inset-0 z-20" 
                            onClick={(e) => { e.stopPropagation(); setOpenDropdownId(null); }}
                          />
                          <div className="origin-top-right absolute right-8 mt-2 w-48 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-30 divide-y divide-gray-100">
                            <div className="py-1">
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/devices/${device.id}`); setOpenDropdownId(null); }}
                                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                View Details
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); setEditModalDevice(device); setOpenDropdownId(null); }}
                                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                Edit
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); setAssignCustomerDevice(device); setOpenDropdownId(null); }}
                                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                Assign Customer
                              </button>
                            </div>
                            <div className="py-1">
                              {device.status !== 'DISABLED' ? (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setConfirmAction({ action: 'DISABLE', device }); setOpenDropdownId(null); }}
                                  className="block w-full text-left px-4 py-2 text-sm text-yellow-700 hover:bg-yellow-50"
                                >
                                  Disable
                                </button>
                              ) : (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setConfirmAction({ action: 'ENABLE', device }); setOpenDropdownId(null); }}
                                  className="block w-full text-left px-4 py-2 text-sm text-green-700 hover:bg-green-50"
                                >
                                  Enable
                                </button>
                              )}
                            </div>
                            <div className="py-1">
                              <button
                                onClick={(e) => { e.stopPropagation(); setConfirmAction({ action: 'DELETE', device }); setOpenDropdownId(null); }}
                                className="block w-full text-left px-4 py-2 text-sm text-red-700 hover:bg-red-50"
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && (
          <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Showing <span className="font-medium">{((data.page - 1) * data.page_size) + 1}</span> to <span className="font-medium">{Math.min(data.page * data.page_size, data.total)}</span> of <span className="font-medium">{data.total}</span> results
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

      {/* Modals */}
      <AddDeviceModal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} />
      {editModalDevice && <EditDeviceModal isOpen={!!editModalDevice} onClose={() => setEditModalDevice(null)} device={editModalDevice} />}
      {assignCustomerDevice && <AssignCustomerModal isOpen={!!assignCustomerDevice} onClose={() => setAssignCustomerDevice(null)} device={assignCustomerDevice} />}
      {confirmAction && <ConfirmActionModal isOpen={!!confirmAction} onClose={() => setConfirmAction(null)} device={confirmAction.device} action={confirmAction.action} />}
    </div>
  );
};
