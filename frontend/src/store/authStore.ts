import { create } from 'zustand';
import { supabase } from '../lib/supabase';
import axios from 'axios';

export interface CurrentUser {
    id: string;
    email: string;
    role: string;
    customer_id: string | null;
    is_active: boolean;
    permissions: string[];
}

interface AuthState {
    user: CurrentUser | null;
    isLoading: boolean;
    error: string | null;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    fetchSession: () => Promise<void>;
}

// Ensure base URL points to backend API in dev
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Setup global axios interceptor so we don't need to pass token manually everywhere
api.interceptors.request.use(async (config) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
    }
    return config;
});

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isLoading: true,
    error: null,
    
    login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
            const { data, error } = await supabase.auth.signInWithPassword({ email, password });
            if (error) throw error;
            
            if (data.session) {
                // Fetch user permissions from backend
                const response = await api.get('/api/v1/users/me');
                set({ user: response.data, isLoading: false });
            }
        } catch (err: any) {
            set({ error: err.message || "Failed to login", isLoading: false });
            throw err;
        }
    },
    
    logout: async () => {
        set({ isLoading: true });
        await supabase.auth.signOut();
        set({ user: null, isLoading: false });
    },
    
    fetchSession: async () => {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (session) {
                const response = await api.get('/api/v1/users/me');
                set({ user: response.data, isLoading: false });
            } else {
                set({ user: null, isLoading: false });
            }
        } catch (err) {
            console.error("Failed to fetch session:", err);
            set({ user: null, isLoading: false });
        }
    }
}));

// Export the configured axios instance for other parts of the app
export { api };
