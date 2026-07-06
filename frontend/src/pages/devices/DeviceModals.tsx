import React, { useState } from 'react';
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { api } from '../../store/authStore';
import { Copy, CheckCircle } from 'lucide-react';

// --- Modals Interfaces ---

export interface AddDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export interface EditDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  device: any;
}

export interface AssignCustomerModalProps {
  isOpen: boolean;
  onClose: () => void;
  device: any;
}

export interface ConfirmActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  device: any;
  action: 'DISABLE' | 'ENABLE' | 'DELETE';
}

// --- Add Device Modal ---

export const AddDeviceModal: React.FC<AddDeviceModalProps> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState({ device_name: '', customer_id: '' });
  const [provisionedData, setProvisionedData] = useState<any>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: customersData, isLoading: isLoadingCustomers } = useQuery({
    queryKey: ['customers', 'list'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/customers?page_size=100');
      return data;
    },
    enabled: isOpen && step === 1,
  });

  const mutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post('/api/v1/devices', payload);
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setProvisionedData(data);
      setStep(2);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  const handleCopy = () => {
    if (provisionedData) {
      navigator.clipboard.writeText(provisionedData.api_key_plaintext);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    setStep(1);
    setForm({ device_name: '', customer_id: '' });
    setProvisionedData(null);
    setAcknowledged(false);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Add New Device">
      {step === 1 ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Device Name</label>
            <input
              required
              type="text"
              value={form.device_name}
              onChange={(e) => setForm({ ...form, device_name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
              placeholder="e.g. Pole-001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Customer</label>
            <select
              required
              value={form.customer_id}
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm bg-white"
            >
              <option value="" disabled>Select a customer...</option>
              {!isLoadingCustomers && customersData?.items.map((c: any) => (
                <option key={c.id} value={c.id}>{c.company_name}</option>
              ))}
            </select>
          </div>
          <div className="pt-4 flex justify-end space-x-3">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating...' : 'Create Device'}
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <CheckCircle className="h-5 w-5 text-green-400" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-green-800">Device Provisioned Successfully</h3>
              </div>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Device UID</label>
            <div className="mt-1 flex rounded-md shadow-sm">
              <span className="inline-flex items-center px-3 rounded-md border border-gray-300 bg-gray-50 text-gray-900 sm:text-sm font-mono w-full">
                {provisionedData?.device_uid}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Key <span className="text-red-500">*</span></label>
            <p className="text-xs text-gray-500 mb-2">This is the ONLY time this key will be displayed. Please save it securely.</p>
            <div className="mt-1 flex rounded-md shadow-sm relative">
              <input
                type="text"
                readOnly
                value={provisionedData?.api_key_plaintext || ''}
                className="flex-1 min-w-0 block w-full px-3 py-2 rounded-none rounded-l-md border border-gray-300 bg-gray-50 text-gray-900 sm:text-sm font-mono"
              />
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center px-3 py-2 border border-l-0 border-gray-300 rounded-r-md bg-gray-100 text-gray-700 hover:bg-gray-200"
              >
                {copied ? <CheckCircle className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id="acknowledged"
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="focus:ring-primary-500 h-4 w-4 text-primary-600 border-gray-300 rounded"
              />
            </div>
            <div className="ml-3 text-sm">
              <label htmlFor="acknowledged" className="font-medium text-gray-700">
                I have securely saved the API key.
              </label>
            </div>
          </div>

          <div className="pt-4 flex justify-end">
            <button
              type="button"
              disabled={!acknowledged}
              onClick={handleClose}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
};

// --- Edit Device Modal ---

export const EditDeviceModal: React.FC<EditDeviceModalProps> = ({ isOpen, onClose, device }) => {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    device_name: device?.device_name || '',
    installation_location: device?.installation_location || '',
    upload_interval_seconds: device?.upload_interval_seconds ?? 300
  });

  const mutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.put(`/api/v1/devices/${device.id}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      onClose();
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({ ...form, upload_interval_seconds: Number(form.upload_interval_seconds) });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit Device: ${device?.device_uid}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Device Name</label>
          <input
            required
            type="text"
            value={form.device_name}
            onChange={(e) => setForm({ ...form, device_name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Installation Location</label>
          <input
            type="text"
            value={form.installation_location}
            onChange={(e) => setForm({ ...form, installation_location: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Upload Interval (seconds)</label>
          <input
            required
            type="number"
            min={30}
            max={86400}
            value={form.upload_interval_seconds}
            onChange={(e) => setForm({ ...form, upload_interval_seconds: e.target.value as any })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
          <p className="mt-1 text-xs text-gray-500">The device is told this on its next upload. It's also used to detect offline devices (3 missed uploads).</p>
        </div>
        <div className="pt-4 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
          <button type="submit" disabled={mutation.isPending} className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-primary-600 hover:bg-primary-700">
            {mutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

// --- Assign Customer Modal ---

export const AssignCustomerModal: React.FC<AssignCustomerModalProps> = ({ isOpen, onClose, device }) => {
  const queryClient = useQueryClient();
  const [customerId, setCustomerId] = useState(device?.customer_id || '');

  const { data: customersData, isLoading } = useQuery({
    queryKey: ['customers', 'list'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/customers?page_size=100');
      return data;
    },
    enabled: isOpen,
  });

  const mutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.put(`/api/v1/devices/${device.id}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      onClose();
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customerId !== device?.customer_id) {
      mutation.mutate({ customer_id: customerId });
    } else {
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Assign Customer: ${device?.device_uid}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Select Customer</label>
          <select
            required
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm bg-white"
          >
            {!isLoading && customersData?.items.map((c: any) => (
              <option key={c.id} value={c.id}>{c.company_name}</option>
            ))}
          </select>
        </div>
        <div className="pt-4 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
          <button type="submit" disabled={mutation.isPending} className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-primary-600 hover:bg-primary-700">
            {mutation.isPending ? 'Saving...' : 'Assign'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

// --- Confirm Action Modal (Disable/Enable/Delete) ---

export const ConfirmActionModal: React.FC<ConfirmActionModalProps> = ({ isOpen, onClose, device, action }) => {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async () => {
      if (action === 'DELETE') {
        await api.delete(`/api/v1/devices/${device.id}`);
      } else {
        // Re-enabled devices start OFFLINE; the next telemetry upload
        // promotes them to ONLINE (and the watchdog keeps status honest).
        const status = action === 'DISABLE' ? 'DISABLED' : 'OFFLINE';
        await api.put(`/api/v1/devices/${device.id}`, { status });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      onClose();
    }
  });

  const getDetails = () => {
    switch (action) {
      case 'DELETE':
        return { title: 'Delete Device', btn: 'Delete', color: 'bg-red-600 hover:bg-red-700', msg: 'Are you sure you want to permanently delete this device? This action cannot be undone.' };
      case 'DISABLE':
        return { title: 'Disable Device', btn: 'Disable', color: 'bg-yellow-600 hover:bg-yellow-700', msg: 'Are you sure you want to disable this device? It will stop processing telemetry.' };
      case 'ENABLE':
        return { title: 'Enable Device', btn: 'Enable', color: 'bg-green-600 hover:bg-green-700', msg: 'Are you sure you want to re-enable this device?' };
    }
  };

  const details = getDetails();

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={details.title}>
      <div className="space-y-4">
        <p className="text-sm text-gray-600">{details.msg}</p>
        <div className="bg-gray-50 p-3 rounded text-sm border border-gray-200">
          <strong>Device UID:</strong> {device?.device_uid}<br />
          <strong>Device Name:</strong> {device?.device_name}
        </div>
        <div className="pt-4 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className={`px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white ${details.color}`}>
            {mutation.isPending ? 'Processing...' : details.btn}
          </button>
        </div>
      </div>
    </Modal>
  );
};
