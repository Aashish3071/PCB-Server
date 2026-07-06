import axios from 'axios';
import { env } from '../config/env';

export const apiClient = axios.create({
  baseURL: env.API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Future interceptors for Auth can be attached here.
