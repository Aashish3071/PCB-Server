import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../store/authStore';
import { X } from 'lucide-react';

interface CustomerModalsProps {
  isAddOpen: boolean;
  setIsAddOpen: (v: boolean) => void;
  editCustomer: any;
  setEditCustomer: (v: any) => void;
}

export const CustomerModals: React.FC<CustomerModalsProps> = ({ 
  isAddOpen, 
  setIsAddOpen, 
  editCustomer, 
  setEditCustomer 
}) => {
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    company_name: '',
    contact_person: '',
    contact_email: '',
    contact_phone: '',
    address: ''
  });

  useEffect(() => {
    if (editCustomer) {
      setFormData({
        company_name: editCustomer.company_name || '',
        contact_person: editCustomer.contact_person || '',
        contact_email: editCustomer.contact_email || '',
        contact_phone: editCustomer.contact_phone || '',
        address: editCustomer.address || ''
      });
    } else {
      setFormData({
        company_name: '',
        contact_person: '',
        contact_email: '',
        contact_phone: '',
        address: ''
      });
    }
  }, [editCustomer, isAddOpen]);

  const addMutation = useMutation({
    mutationFn: async (data: any) => {
      await api.post('/api/v1/customers', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      setIsAddOpen(false);
    },
    onError: () => alert('Failed to create customer')
  });

  const editMutation = useMutation({
    mutationFn: async (data: any) => {
      await api.put(`/api/v1/customers/${editCustomer.id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      setEditCustomer(null);
    },
    onError: () => alert('Failed to update customer')
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editCustomer) {
      editMutation.mutate(formData);
    } else {
      addMutation.mutate(formData);
    }
  };

  const isOpen = isAddOpen || !!editCustomer;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        <div className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" onClick={() => { setIsAddOpen(false); setEditCustomer(null); }} />

        <div className="relative inline-block w-full max-w-md p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-lg">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-lg font-medium leading-6 text-gray-900">
              {editCustomer ? 'Edit Customer' : 'Add Customer'}
            </h3>
            <button
              onClick={() => { setIsAddOpen(false); setEditCustomer(null); }}
              className="text-gray-400 hover:text-gray-500 focus:outline-none"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Company Name *</label>
              <input
                type="text"
                required
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={formData.company_name}
                onChange={e => setFormData({...formData, company_name: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Contact Person</label>
              <input
                type="text"
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={formData.contact_person}
                onChange={e => setFormData({...formData, contact_person: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={formData.contact_email}
                onChange={e => setFormData({...formData, contact_email: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Phone</label>
              <input
                type="text"
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={formData.contact_phone}
                onChange={e => setFormData({...formData, contact_phone: e.target.value})}
              />
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => { setIsAddOpen(false); setEditCustomer(null); }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={addMutation.isPending || editMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white border border-transparent rounded-md shadow-sm bg-primary-600 hover:bg-primary-700 focus:outline-none disabled:opacity-50"
              >
                {addMutation.isPending || editMutation.isPending ? 'Saving...' : 'Save Customer'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
