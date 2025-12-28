import { getWorkflows, getConnectors, getRuns } from '../src/lib/api/client';

describe('API Client Smoke Tests', () => {
  // Set mock mode for tests
  beforeAll(() => {
    process.env.NEXT_PUBLIC_MOCK_API = 'true';
  });

  test('getWorkflows() returns at least 1 workflow with required fields', async () => {
    const workflows = await getWorkflows();
    
    expect(workflows.length).toBeGreaterThanOrEqual(1);
    
    const workflow = workflows[0];
    expect(workflow).toHaveProperty('name');
    expect(workflow).toHaveProperty('version');
    expect(workflow).toHaveProperty('description');
    expect(typeof workflow.name).toBe('string');
    expect(typeof workflow.version).toBe('string');
    expect(typeof workflow.description).toBe('string');
  });

  test('getConnectors() returns at least 1 connector with required fields', async () => {
    const connectors = await getConnectors();
    
    expect(connectors.length).toBeGreaterThanOrEqual(1);
    
    const connector = connectors[0];
    expect(connector).toHaveProperty('id');
    expect(connector).toHaveProperty('type');
    expect(connector).toHaveProperty('name');
    expect(typeof connector.id).toBe('string');
    expect(typeof connector.type).toBe('string');
    expect(typeof connector.name).toBe('string');
  });

  test('getRuns() returns at least 1 run with required fields', async () => {
    const runs = await getRuns();
    
    expect(runs.length).toBeGreaterThanOrEqual(1);
    
    const run = runs[0];
    expect(run).toHaveProperty('runId');
    expect(run).toHaveProperty('status');
    expect(run).toHaveProperty('startedAt');
    expect(typeof run.runId).toBe('string');
    expect(typeof run.status).toBe('string');
    expect(typeof run.startedAt).toBe('string');
  });
});
