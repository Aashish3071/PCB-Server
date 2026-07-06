# PCB Server - Operator Guide

Welcome to the PCB Server Administration Portal. This guide provides step-by-step instructions for operators managing Solar Street Light RMS devices.

## 1. Login
1. Navigate to the portal URL provided by your administrator.
2. Enter your email and password.
3. Upon successful login, you will be redirected to the **Dashboard**, which provides a high-level overview of the fleet.

## 2. Customer Creation
Before adding devices, you must create a Customer profile.
1. Navigate to **Customers** in the sidebar.
2. Click **Add Customer**.
3. Fill in the required details: Company Name, Contact Person, Email, and Phone.
4. Click **Save**.

## 3. Device Provisioning
1. Navigate to **Devices** in the sidebar.
2. Click **Add Device**.
3. Select the Customer you created in Step 2.
4. Enter a descriptive Device Name and optional Installation Location.
5. Click **Provision Device**.

## 4. API Key Handling
**CRITICAL**: Immediately after provisioning a device, the system will display the unique **Device UID** and **API Key**.
- This is the **ONLY** time the plaintext API Key will be visible.
- Copy and securely store the API Key (e.g., in a password manager or directly flash it to the physical device).
- You must click the acknowledgment checkbox before closing the modal.

## 5. Controller Connection
To connect a physical controller to the server, configure its firmware with:
- **Endpoint URL**: `https://<YOUR_API_DOMAIN>/api/v1/telemetry`
- **Headers**:
  - `X-Device-UID`: The generated Device UID
  - `X-API-Key`: The generated plaintext API Key

For the complete end-to-end walkthrough (provision → put credentials on the
device → test with `curl` → verify Online), see
**[hardware_connection_guide.md](hardware_connection_guide.md)**.

Full firmware contract (payload schema, response codes, reference Arduino /
MicroPython implementations, smoke-test checklist) is in
**[firmware_integration.md](firmware_integration.md)** — give this to whoever
writes the device firmware.

## 6. Telemetry Verification
1. Once the controller is connected and transmitting, navigate to **Devices**.
2. The device Status should change from `PROVISIONED` to `ONLINE`.
3. Click on the device row to open **Device Details**.
4. Verify that the **Current Sensor Values** (Battery, Signal, Voltage) are updating.
5. You can also view the full historical data in the **Fleet Telemetry** page.

## 7. Alert Resolution
If a device reports critical conditions (e.g., Low Battery, Offline), an alert is generated.
1. Navigate to **Alerts** in the sidebar.
2. Review the Active alerts.
3. After addressing the underlying issue (e.g., physically inspecting the device), click **Resolve** on the alert row.

## 8. JSON Export
To export data for external reporting or analysis:
1. Navigate to the **Fleet Telemetry** page.
2. Use the filters (Date, Customer, Device) to narrow down the dataset.
3. Click **Export JSON**.

## 9. Tuning the Upload Interval (server → device control)
Each device has an **Upload Interval** (default 300s). The server hands it
back to the device on every telemetry response as `next_upload_seconds`, so
changing it in the dashboard actually retunes the hardware — **no reflash
needed**.

1. Navigate to **Devices** and click the ⋯ menu on the row → **Edit**.
2. Set **Upload Interval (seconds)** to anywhere from 30 to 86400.
3. Save. The device picks up the new cadence on its next upload.
4. The offline watchdog automatically scales with this: a device is marked
   OFFLINE after 3 missed intervals.

## 10. Basic Troubleshooting
- **Device Offline**: check power/signal first. The server marks a device
  OFFLINE after 3 missed uploads based on its own `upload_interval_seconds`
  — a slow reporter (say, every hour) has a much wider grace window than a
  fast one.
- **Authentication Failure**: rotate the key from the device's Details page,
  then re-flash. The old key is invalidated immediately.
- **Rate limit / 429**: a device is uploading faster than allowed — usually a
  firmware bug that ignores `next_upload_seconds`. See
  [firmware_integration.md](firmware_integration.md#response-codes-and-what-firmware-should-do).
- **Disabled Device**: retired/compromised devices should be Disabled from
  the Details page. All subsequent telemetry gets `403`.

## 11. Server-side diagnostics (for admins)
When something looks off at the fleet level (not one device), see
**[operations.md](operations.md)** for `/api/v1/diagnostics`, log filters, and
common incident playbooks.
