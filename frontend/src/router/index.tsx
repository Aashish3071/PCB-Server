import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { Dashboard } from '../pages/Dashboard';
import { DeviceList } from '../pages/devices/DeviceList';
import { DeviceDetails } from '../pages/devices/DeviceDetails';
import { CustomerList } from '../pages/customers/CustomerList';
import { AlertList } from '../pages/alerts/AlertList';
import { FleetTelemetry } from '../pages/telemetry/FleetTelemetry';
import { SystemHealth } from '../pages/health/SystemHealth';
import { Login } from '../pages/Login';
import { ProtectedRoute } from '../components/ProtectedRoute';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          {
            index: true,
            element: <Dashboard />,
          },
          { path: 'devices', element: <DeviceList /> },
          { path: 'devices/:id', element: <DeviceDetails /> },
          { path: 'customers', element: <CustomerList /> },
          { path: 'alerts', element: <AlertList /> },
          { path: 'telemetry', element: <FleetTelemetry /> },
          { path: 'health', element: <SystemHealth /> },
          { path: 'settings', element: <div className="p-4">Settings Placeholder</div> },
        ],
      },
    ],
  },
]);
