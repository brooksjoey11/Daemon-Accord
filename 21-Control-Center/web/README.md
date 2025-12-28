# Daemon Accord Control Center - Web GUI

Next.js-based web interface for managing the Daemon Accord platform.

## Structure

This is the GUI module located at `21-Control-Center/web/`. The parent directory `21-Control-Center/` also contains:
- `src/control_center/` - Server-side control center core (future)

## Setup

### Prerequisites
- Node.js 18+ 
- npm

### Installation

```bash
cd 21-Control-Center/web
npm install
```

## Running

### Development Mode

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Environment Variables

### Mock Mode (Default)

By default, the GUI runs in **mock mode** using deterministic mock data:

```bash
# Mock mode is enabled by default
# No environment variables needed
```

### Live Mode (Connect to Backend)

To connect to the actual Daemon Accord backend:

```bash
# .env.local
NEXT_PUBLIC_MOCK_API=false
NEXT_PUBLIC_DAEMON_ACCORD_API_BASE=http://localhost:8082
```

## Mock vs Real Mode

- **Mock Mode** (`NEXT_PUBLIC_MOCK_API=true` or unset):
  - Uses deterministic mock data from `src/lib/api/mockData.ts`
  - No backend connection required
  - Shows "Mock Mode" badge in UI
  - Perfect for development and UI work

- **Live Mode** (`NEXT_PUBLIC_MOCK_API=false`):
  - Connects to Daemon Accord Control Plane API
  - Requires backend running at `NEXT_PUBLIC_DAEMON_ACCORD_API_BASE`
  - Real data from the platform

## Pages

- `/` - Dashboard: Overview, status tiles, recent runs
- `/workflows` - Workflows: List and manage automation workflows
- `/connectors` - Connectors: Manage integrations and data connectors
- `/runs` - Runs: View execution history and job runs
- `/settings` - Settings: Environment configuration and integration status

## Testing

```bash
npm test
```

Runs smoke tests that verify:
- `getWorkflows()` returns workflows with `name`, `version`, `description`
- `getConnectors()` returns connectors with `id`, `type`, `name`
- `getRuns()` returns runs with `runId`, `status`, `startedAt`

## Linting

```bash
npm run lint
```

## Build

```bash
npm run build
```

## Architecture

### API Layer
- `src/lib/api/client.ts` - API client with mock/real mode switching
- `src/lib/api/mockData.ts` - Deterministic mock data

### Components
- `src/components/shell/` - Shell layout (Sidebar, TopBar, Shell)
- `src/components/ui/` - Reusable UI components (Button, Card, Badge)

### Pages
- `src/app/(shell)/` - All pages with shell layout
  - `page.tsx` - Dashboard
  - `workflows/page.tsx` - Workflows
  - `connectors/page.tsx` - Connectors
  - `runs/page.tsx` - Runs
  - `settings/page.tsx` - Settings

## Development Notes

- Uses Next.js 14+ App Router
- TypeScript for type safety
- Tailwind CSS for styling
- Mock-first approach allows UI development without backend
- Clean empty states (no lorem ipsum)
- Responsive design (desktop + mobile)
